from datetime import timedelta, datetime
from collections import defaultdict
import logging

from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_STATES = [
    ("draft", "Draft"),
    ("to_approve", "To be approved"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("done", "Done"),
]

class MaterialRequest(models.Model):
    _name = 'apm.material.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Material Request'
    _order = "id desc"
    _check_company_auto = True

    @api.model
    def _get_random_approver(self):
        warehouse_group = self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
        if not warehouse_group:
            return None
        return warehouse_group.users[-1] if warehouse_group.users else None
    
    @api.model
    def _get_default_warehouse(self):
        """get default warehouse"""
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
    
    name = fields.Char(
        string="Request Number",
        required=True,
        default=lambda self: _("New"),
        tracking=True,
        copy=False,
    )
    
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda s: s.env.company.id, index=True)
    
    has_insufficient_stock = fields.Boolean(
        string='Insufficient Stock',
        compute='_compute_insufficient_stock',
        store=True,
        help="Ada line dengan quantity > stock available"
    )

    purchase_request_id = fields.Many2one(
        'purchase.request',
        string='Auto Purchase Request',
        readonly=True,
        copy=False,
        help="Purchase Request otomatis untuk insufficient stock"
    )

    insufficient_stock_qty = fields.Float(
        string='Shortage Qty Total',
        compute='_compute_insufficient_stock',
        store=True,
        help="Total shortage quantity dari semua lines"
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        tracking=True,
        check_company=True,
        related='requested_by_id.employee_id.department_id',
        help="Department yang mengajukan material request"
    )
    
    purchase_type = fields.Selection(
        selection=[
            ('kapal', 'Kapal'),
            ('ga', 'G&A'),
        ],
        string='Jenis Pembelian',
        required=True,
        tracking=True,
        default='ga',
        help="Jenis pembelian: Kapal (untuk operasional kapal) atau G&A (General & Administration)"
    )
    
    vessel_id = fields.Many2one(
        'kapal.master',
        string='Vessel Name',
        tracking=True,
        help="Nama kapal untuk material request jenis Kapal"
    )
    # === END FIELD BARU ===
    
    requested_by_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        copy=False,
        tracking=True,
        default=lambda self: self.env.user,
        index=True,
    )
    assigned_to_id = fields.Many2one(
        comodel_name="res.users",
        string="Approver WH",
        default=lambda self: self._get_random_approver(),
        required=True,
        tracking=True
    )
    request_date = fields.Date(
        string="Request Date",
        help="Date when the user initiated the request.",
        default=fields.Date.context_today,
        tracking=True,
    )
    date_from = fields.Date('Start Date', index=True, copy=False, default=fields.Date.context_today, tracking=True, required=True)
    date_to = fields.Date('End Date', copy=False, tracking=True)
    number_of_days = fields.Float(
        'Number of Days', compute='_compute_number_of_days', inverse='_inverse_number_of_days',
        store=True, readonly=False, tracking=True, default=0.0,
        help='Duration in days. Reference field to use when necessary.')
    
    request_type = fields.Selection(
        selection=[
            ('inventory', 'Issue Material'),
            ('internal', 'Transfer')
        ], 
        string='Request Type',
        required=True
    )
    
    description = fields.Text()
    
    request_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        required=True,
        tracking=True,
        index=True,
        string="Request From WH",
        default=lambda self: self._get_default_warehouse(),
        check_company=True,
    )

    destination_id = fields.Many2one(
        comodel_name="stock.warehouse",
        required=True,
        tracking=True,
        index=True,
        string="Destination WH",
        check_company=True,
        related='vessel_id.destination_id'
    )

    # ✅ SEMUA FIELD PICKING INFO DIPERJAGA
    location_id = fields.Many2one(
        comodel_name="stock.location",
        copy=False,
        index=True,
        compute='_compute_picking_information',
        store=True
    )

    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        copy=False,
        index=True,
        compute='_compute_picking_information',
        store=True,
    )
    return_picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        copy=False,
        index=True,
        compute='_compute_picking_information',
        store=True,
    )
    
    location_dest_id = fields.Many2one(
        comodel_name="stock.location",
        copy=False,
        index=True,
        compute='_compute_picking_information',
        store=True
    )
    
    # === SEMUA COMPUTED FIELD DIPERJAGA ===
    request_summary = fields.Char(
        string='Request Summary',
        compute='_compute_request_summary',
        store=True,
        help="Summary otomatis dari department, jenis pembelian, dan vessel"
    )
    
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        copy=False,
        default="draft",
    )    
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    
    delivery_status = fields.Selection([
        ('pending', 'Not Delivered'),
        ('partial', 'Partially Delivered'),
        ('full', 'Fully Delivered'),
    ], string='Delivery Status', compute='_compute_delivery_status', store=True)
    
    line_ids = fields.One2many(
        comodel_name="apm.material.request.line",
        inverse_name="request_id",
        string="Material to Request",
        copy=False,
        tracking=True,
        required=True 
    )
    
    picking_ids = fields.Many2many('stock.picking', string='Transfers', compute='_compute_stock_picking', search='_search_stock_picking')
    picking_count = fields.Integer(compute='_compute_stock_picking')
    
    mr_status = fields.Selection(selection=[
        ('return', 'Return'), 
        ('pickup', 'Pickup'), 
        ('returned', 'Returned')
        ],compute='_compute_mr_status', string='MR Status')
    is_late = fields.Boolean(
        string="Is overdue",
        help="The products haven't been picked-up or returned in time",
        compute='_compute_is_late',
    )
    next_action_date = fields.Datetime(string="Next Action", compute='_compute_mr_status')
    has_pickable_lines = fields.Boolean(compute='_compute_has_action_lines')
    has_returnable_lines = fields.Boolean(compute='_compute_has_action_lines')
    mr_status_info = fields.Char(compute='_compute_mr_late_ifo')

    purchase_request_count = fields.Integer(
    string="Purchase Request Count",
    compute="_compute_purchase_request_count",
    store=False,
)

    @api.depends('purchase_request_id')
    def _compute_purchase_request_count(self):
        for record in self:
            record.purchase_request_count = 1 if record.purchase_request_id else 0
    
    @api.depends('line_ids.product_id', 'line_ids.product_uom_qty', 'request_warehouse_id', 'location_id')
    def _compute_insufficient_stock(self):
        """Compute insufficient stock status & total shortage"""
        for record in self:
            insufficient_lines = record.env['apm.material.request.line']
            total_shortage = 0.0

            for line in record.line_ids.filtered(lambda l: l.product_uom_qty > 0):
                # GET AVAILABLE STOCK - Use consistent warehouse context
                # Prioritize warehouse over location for consistent stock checking
                stock_context = {'warehouse': record.request_warehouse_id.id}

                # Only add location context if location_id is properly set and valid
                if record.location_id:
                    try:
                        stock_context['location'] = record.location_id.id
                    except:
                        # If location_id is invalid, don't use it
                        pass

                available_qty = line.product_id.with_context(stock_context).qty_available

                if line.product_uom_qty > available_qty:
                    shortage = line.product_uom_qty - available_qty
                    total_shortage += shortage
                    insufficient_lines |= line

            record.has_insufficient_stock = bool(insufficient_lines)
            record.insufficient_stock_qty = total_shortage
            
    @api.depends('department_id', 'purchase_type', 'vessel_id')
    def _compute_request_summary(self):
        """Compute summary dari department, purchase_type, dan vessel"""
        for record in self:
            summary_parts = []
            if record.department_id:
                summary_parts.append(record.department_id.name)
            if record.purchase_type:
                type_label = dict(self._fields['purchase_type'].selection).get(record.purchase_type, '')
                summary_parts.append(type_label)
            if record.vessel_id:
                summary_parts.append(record.vessel_id.name)
            
            record.request_summary = ' → '.join(summary_parts) if summary_parts else ''
    
    # ✅ FIXED: _compute_picking_information dengan FALLBACK
    @api.depends('request_warehouse_id', 'request_type', 'destination_id')
    def _compute_picking_information(self):
        for record in self:
            if record.state == 'done':
                continue
            
            record = record.with_company(record.company_id)
            
            # ✅ PICKING TYPE
            record.picking_type_id = record._search_picking_type(record.request_warehouse_id)
            record.return_picking_type_id = record._search_picking_type(record.destination_id)

            # ✅ LOCATIONS DENGAN FALLBACK
            if record.picking_type_id:
                record.location_id = record.picking_type_id.default_location_src_id.id
                record.location_dest_id = record.picking_type_id.default_location_dest_id.id
            else:
                # FALLBACK: Gunakan warehouse stock locations
                source_wh = record.request_warehouse_id
                dest_wh = record.destination_id or source_wh
                
                source_loc = source_wh.lot_stock_id
                dest_loc = dest_wh.lot_stock_id or source_loc
                
                if not source_loc:
                    source_loc = self.env['stock.location'].search([
                        ('usage', '=', 'internal'),
                        ('company_id', '=', record.company_id.id)
                    ], limit=1)
                
                record.location_id = source_loc.id
                record.location_dest_id = dest_loc.id
    
    def _search_picking_type(self, warehouse):
        """✅ FIXED: Proper picking type search"""
        self.ensure_one()
        if not warehouse:
            return self.env['stock.picking.type']
        
        # Prioritas 1: Warehouse-specific internal type
        picking_type = warehouse.int_type_id
        if picking_type:
            return picking_type
        
        # Prioritas 2: Any internal picking type di warehouse
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', warehouse.id)
        ], limit=1)
        if picking_type:
            return picking_type
        
        # Prioritas 3: Any internal picking type di company
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.company_id.id)
        ], limit=1)
        return picking_type
    
    def _search_location(self, request_type, destination_id):
        """✅ IMPROVED: Better location fallback"""
        if not request_type or not destination_id:
            return False
        
        # Prioritas 1: Picking type locations (jika ada)
        if self.picking_type_id:
            if request_type == 'inventory':
                return self.picking_type_id.default_location_dest_id
            else:
                return self.picking_type_id.default_location_dest_id
        
        # Prioritas 2: Warehouse stock location
        if destination_id.lot_stock_id:
            return destination_id.lot_stock_id
        
        # Prioritas 3: Any internal location
        return self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
    @api.depends("state")
    def _compute_is_editable(self):
        for rec in self:
            rec.is_editable = rec.state != 'draft'
            
    @api.depends('line_ids.move_ids')
    def _compute_stock_picking(self):
        for rec in self:
            picking = rec.line_ids.mapped('move_ids.picking_id')
            pickings = picking | picking.backorder_ids
            rec.picking_ids = pickings
            rec.picking_count = len(pickings)
            
    @api.depends(
        'line_ids.product_uom_qty',
        'line_ids.move_quantity',
        'line_ids.move_returned',
    )
    def _compute_has_action_lines(self):
        self.has_pickable_lines = False
        self.has_returnable_lines = False
        for order in self:
            order_lines = order.line_ids.filtered(lambda line: line.product_id.type != 'combo')
            if order.request_type == 'inventory':
                order.has_pickable_lines = order.has_returnable_lines = False
            else:
                order.has_pickable_lines = any(line.move_quantity < line.product_uom_qty for line in order_lines)
                order.has_returnable_lines = any(line.move_returned < line.move_quantity for line in order_lines)
            
    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_delivery_status(self):
        for order in self:
            if not order.picking_ids or all(p.state == 'cancel' for p in order.picking_ids):
                order.delivery_status = False
            elif all(p.state in ['done', 'cancel'] for p in order.picking_ids):
                order.delivery_status = 'full'
            elif any(p.state == 'done' for p in order.picking_ids):
                order.delivery_status = 'partial'
            else:
                order.delivery_status = 'pending'
    
    @api.depends('next_action_date', 'mr_status')
    def _compute_is_late(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_late = (
                rec.mr_status in ['pickup', 'return']
                and rec.next_action_date
                and rec.next_action_date < now
            )
        
    @api.depends('picking_ids.state', 'date_from', 'date_to')
    def _compute_mr_status(self):
        for order in self:
            order.next_action_date = False
            if not order.picking_ids or order.request_type == 'inventory':
                order.mr_status = False
            elif order.has_returnable_lines:
                order.mr_status = 'return'
                order.next_action_date = order.date_to
            elif order.has_pickable_lines:
                order.mr_status = 'pickup'
                order.next_action_date = order.date_from
            else:
                order.mr_status = 'returned'
    
    @api.depends('mr_status', 'is_late')
    def _compute_mr_late_ifo(self):
        for rec in self:
            if rec.mr_status == 'pickup' and rec.is_late:
                rec.mr_status_info = 'Late Pickup'
            elif rec.mr_status == 'pickup' and not rec.is_late:
                rec.mr_status_info = 'Booked'
            elif rec.mr_status == 'return' and rec.is_late:
                rec.mr_status_info = 'Picked-up'
            elif rec.mr_status == 'return' and not rec.is_late:
                rec.mr_status_info = 'Late Return'
            elif rec.mr_status == 'returned':
                rec.mr_status_info =  'Returned'
            else:
                rec.mr_status_info = False
            
    @api.depends('date_from', 'date_to')
    def _compute_number_of_days(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                duration = rec.date_to - rec.date_from
                rec.number_of_days = duration.days
            else:
                rec.number_of_days = 0
            
    def _inverse_number_of_days(self):
        for rec in self:
            if rec.date_from and rec.number_of_days:
                rec.date_to = rec.date_from + timedelta(days=int(rec.number_of_days))
            
    # === ONCHANGE & CONSTRAINTS ===
    @api.onchange('purchase_type')
    def _onchange_purchase_type(self):
        """Clear vessel_id saat purchase_type berubah"""
        if self.purchase_type != 'kapal':
            self.vessel_id = False
    
    @api.constrains('department_id', 'company_id')
    def _check_department_company(self):
        """Validasi department sesuai company"""
        for record in self:
            if record.department_id and record.department_id.company_id and record.department_id.company_id != record.company_id:
                raise UserError(
                    _("Department '%s' tidak termasuk dalam company '%s'.\n"
                      "Pilih department yang sesuai dengan company.") % 
                    (record.department_id.name, record.company_id.name)
                )
    
    @api.constrains('date_from', 'date_to')
    def _check_date_from_date_to(self):
        if any(rec.date_to and rec.date_from > rec.date_to for rec in self):
            raise UserError(_("The Start Date of the Validity Period must be anterior to the End Date."))
    
    @api.model
    def create(self, vals):
        """Override create untuk set default values berdasarkan user"""
        # Set default department berdasarkan user department
        if 'department_id' not in vals and self.env.user.employee_id:
            employee_dept = self.env.user.employee_id.department_id
            if employee_dept and (not employee_dept.company_id or employee_dept.company_id == self.env.company):
                vals['department_id'] = employee_dept.id
        
        # Set default purchase_type jika belum ada
        if 'purchase_type' not in vals:
            vals['purchase_type'] = 'ga'  # Default G&A
        
        return super(MaterialRequest, self).create(vals)
    
    # === BUTTON METHODS ===
    def button_to_approve(self):
        """Override untuk validasi field tambahan sebelum approval"""
        # Validasi field wajib
        for record in self:
            if not record.department_id:
                raise UserError(_("Department wajib diisi sebelum mengajukan approval."))

            if not record.purchase_type:
                raise UserError(_("Jenis Pembelian wajib diisi sebelum mengajukan approval."))

        # Original logic
        for record in self:
            if record.name == _("New"):
                record.name = self.env['ir.sequence'].next_by_code('apm.material.request') or _("New")

        # Ensure stock computation is consistent before approval
        _logger.info(f"=== BUTTON TO APPROVE: {record.name} ===")
        _logger.info(f"Warehouse: {record.request_warehouse_id.name} (ID: {record.request_warehouse_id.id})")
        _logger.info(f"Location: {record.location_id.name if record.location_id else 'None'} (ID: {record.location_id.id if record.location_id else 'None'})")

        # Force recompute of insufficient stock before approval
        for record in self:
            # Trigger recompute of insufficient stock with current context
            record._compute_insufficient_stock()

            # Log stock status for debugging
            for line in record.line_ids.filtered(lambda l: l.product_uom_qty > 0):
                stock_context = {'warehouse': record.request_warehouse_id.id}
                if record.location_id:
                    try:
                        stock_context['location'] = record.location_id.id
                    except:
                        pass

                available_qty = line.product_id.with_context(stock_context).qty_available
                _logger.info(f"Line {line.product_id.name}: Demand={line.product_uom_qty}, Available={available_qty}")

        self.write({"state": "to_approve"})
                
    def _search_stock_picking(self, operator, value):
        return [('line_ids.move_ids', operator, value)]

    def button_draft(self):
        self.write({"state": "draft"})

    def button_approved(self):
        self.ensure_one()
        
        # VALIDASI
        if not self.line_ids.filtered(lambda l: l.product_uom_qty > 0):
            raise UserError(_("Tidak ada material dengan quantity > 0 untuk diproses."))
        
        if not self.request_warehouse_id:
            raise UserError(_("Warehouse 'Request From' wajib diisi."))
        
        # ✅ AUTO CREATE PURCHASE REQUEST
        if self.has_insufficient_stock:
            purchase_request = self._create_auto_purchase_request()
            _logger.info(f"✅ Auto-created PR {purchase_request.name} untuk {self.insufficient_stock_qty} units")
        
        # LOCATIONS
        source_location = self.location_id
        dest_location = self.location_dest_id
        
        # FALLBACK
        if not source_location:
            source_wh = self.request_warehouse_id
            source_location = source_wh.lot_stock_id or self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        
        if not dest_location:
            dest_wh = self.destination_id or self.request_warehouse_id
            dest_location = dest_wh.lot_stock_id or source_location
        
        if not source_location or not dest_location:
            raise UserError(_(
                "Source Location: %s\n"
                "Dest Location: %s\n"
                "Mohon konfigurasi warehouse terlebih dahulu."
            ) % (source_location.name or 'TIDAK DITEMUKAN', dest_location.name or 'TIDAK DITEMUKAN'))
        
        # CREATE PICKINGS
        delivery, returned = self._prepare_stock_picking()
        
        _logger.info(f"=== APPROVE MR {self.name} ===")
        _logger.info(f"Source Loc: {source_location.name} (ID: {source_location.id})")
        _logger.info(f"Dest Loc: {dest_location.name} (ID: {dest_location.id})")
        
        # DELIVERY PICKING
        picks = self.env['stock.picking'].with_context({
            'is_material_request': True,
            'default_material_request_id': self.id,
        }).create(delivery)
        picks.action_confirm()
        
        _logger.info(f"✅ Created delivery: {picks.name}")
        
        # RETURN PICKING
        if self.request_type == 'internal' and returned:
            returns = self.env['stock.picking'].with_context({
                'is_material_request': True,
                'default_material_request_id': self.id,
            }).create(returned)
            returns.action_confirm()
            
            moves_by_line = defaultdict(lambda: {'picks': self.env['stock.move'], 'returns': self.env['stock.move']})
            
            for move in picks.move_ids:
                if move.state in ('done', 'cancel'):
                    continue
                moves_by_line[move.material_request_line_id]['picks'] |= move
                
            for move in returns.move_ids:
                if move.state in ('done', 'cancel'):
                    continue
                moves_by_line[move.material_request_line_id]['returns'] |= move
            
            returns.move_ids._do_unreserve()
            for moves in moves_by_line.values():
                if moves['returns']:
                    moves['returns'].write({
                        'move_orig_ids': [Command.link(pick.id) for pick in moves['picks']],
                        'procure_method': 'make_to_order',
                    })
            
            returns.return_id = picks
            returns.move_ids._recompute_state()
            _logger.info(f"✅ Created return: {returns.name}")
        
        # UPDATE STATE
        self.write({"state": "approved"})
        # ✅ NO RETURN - ODOO AUTO-REFRESH FORM

    def _create_auto_purchase_request(self):
        """Create PR untuk insufficient stock lines"""
        # Use consistent stock checking logic
        stock_context = {'warehouse': self.request_warehouse_id.id}
        if self.location_id:
            try:
                stock_context['location'] = self.location_id.id
            except:
                pass

        insufficient_lines = self.line_ids.filtered(lambda l: l.product_uom_qty > 0 and
                                                l.product_uom_qty > l.product_id.with_context(stock_context).qty_available)

        if not insufficient_lines:
            return False

        # CREATE PURCHASE REQUEST
        purchase_request = self.env['purchase.request'].create({
            'material_request_id': self.id,
            'date_start': fields.Datetime.now(),
        })

        # CREATE PURCHASE LINES
        purchase_lines = []
        for line in insufficient_lines:
            available_qty = line.product_id.with_context(stock_context).qty_available
            shortage_qty = line.product_uom_qty - available_qty

            purchase_lines.append(Command.create({
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'product_qty': shortage_qty,
                'material_request_line_id': line.id,
                'description': f"Shortage MR {self.name}: {line.name or line.product_id.name}",
            }))

        purchase_request.write({'line_ids': purchase_lines})
        self.purchase_request_id = purchase_request.id

        # AUTO SUBMIT
        purchase_request.button_to_approve()

        # POST MESSAGE
        self.message_post(
            body=f"Purchase Request <b>{purchase_request.name}</b> created untuk {len(insufficient_lines)} items:<br/>{', '.join(purchase_request.line_ids.mapped('product_id.name'))}",
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )

        return purchase_request

    def button_rejected(self):
        self.write({"state": "draft"})
    
    def button_rejected_to_be_approved(self):
        self.write({"state": "rejected"})

    def button_done(self):
        self.ensure_one()
        self.write({"state": "done"})
        
    # === FIXED: _prepare_stock_picking ===
    def _prepare_stock_picking(self):
        """✅ FIXED: Return (delivery_dict, returned_dict_or_False) + EXPLICIT LOCATIONS"""
        self.ensure_one()
        
        # GET LOCATIONS FROM COMPUTED FIELDS + FALLBACK
        source_location = self.location_id
        dest_location = self.location_dest_id
        
        # FINAL FALLBACK
        if not source_location:
            source_wh = self.request_warehouse_id
            source_location = source_wh.lot_stock_id or self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        
        if not dest_location:
            dest_wh = self.destination_id or self.request_warehouse_id
            dest_location = dest_wh.lot_stock_id or source_location
        
        # PICKING TYPE
        picking_type = self.picking_type_id
        if not picking_type:
            picking_type = self.request_warehouse_id.int_type_id or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id.company_id', '=', self.company_id.id)
            ], limit=1)
        
        if not picking_type:
            raise UserError(_("Internal Transfer picking type tidak ditemukan!"))
        
        # ORIGIN
        origin_parts = [self.name]
        if self.department_id:
            origin_parts.append(f"Dept:{self.department_id.name[:8]}")
        if self.purchase_type == 'kapal' and self.vessel_id:
            origin_parts.append(f"V:{self.vessel_id.name[:8]}")
        origin = " / ".join(origin_parts)
        
        # ✅ DELIVERY PICKING - EXPLICIT LOCATIONS
        delivery = {
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,           # ✅ FROM COMPUTED/FALLBACK
            'location_dest_id': dest_location.id,        # ✅ FROM COMPUTED/FALLBACK
            'partner_id': self.assigned_to_id.partner_id.id or False,
            'origin': origin,
            'scheduled_date': self.date_from,
            'date': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'move_ids_without_package': [
                Command.create({
                    **line._prepare_stock_move(),
                    'location_id': source_location.id,        # ✅ CRITICAL: EXPLICIT
                    'location_dest_id': dest_location.id,     # ✅ CRITICAL: EXPLICIT
                    'warehouse_id': self.request_warehouse_id.id,
                })
                for line in self.line_ids.filtered(lambda l: l.product_uom_qty > 0)
            ],
        }
        
        # ✅ RETURN PICKING (INTERNAL ONLY)
        returned = False
        if (self.request_type == 'internal' and 
            self.destination_id and 
            self.destination_id != self.request_warehouse_id):
            
            return_picking_type = self.return_picking_type_id or picking_type
            
            # REVERSE LOCATIONS
            return_source_loc = dest_location
            return_dest_loc = source_location
            
            returned = {
                'picking_type_id': return_picking_type.id,
                'location_id': return_source_loc.id,         # ✅ REVERSE
                'location_dest_id': return_dest_loc.id,      # ✅ REVERSE
                'partner_id': self.assigned_to_id.partner_id.id or False,
                'origin': f"RETURN-{origin}",
                'scheduled_date': self.date_to or (fields.Datetime.now() + timedelta(days=7)),
                'date': fields.Datetime.now(),
                'company_id': self.company_id.id,
                'move_ids_without_package': [
                    Command.create({
                        **line._prepare_return_move(),
                        'location_id': return_source_loc.id,     # ✅ REVERSE
                        'location_dest_id': return_dest_loc.id,  # ✅ REVERSE
                        'warehouse_id': self.destination_id.id,
                    })
                    for line in self.line_ids.filtered(lambda l: l.product_uom_qty > 0)
                ],
            }
        
        _logger.info(f"Delivery moves: {len(delivery['move_ids_without_package'])}")
        if returned:
            _logger.info(f"Return moves: {len(returned['move_ids_without_package'])}")
        
        return delivery, returned
    
    def action_view_stock_picking(self, pickings=False):
        if not pickings:        
            pickings = self.mapped('picking_ids')
        
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_incoming')
        if self.request_type == 'internal':
            action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_internal')
        
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif len(pickings) == 1:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action
    
    # def action_view_purchase_request(self):
    #     """Menampilkan Purchase Request terkait"""
    #     self.ensure_one()
        
    #     purchase_request = self.purchase_request_id
    #     if not purchase_request:
    #         return {'type': 'ir.actions.act_window_close'}

    #     try:
    #         # Try to get the action
    #         action = self.env['ir.actions.actions']._for_xml_id('purchase_request.view_purchase_request_form')
    #     except ValueError as e:
    #         _logger.error(f"Action 'purchase_request.view_purchase_request_form' not found: {e}")
    #         raise UserError(_("Purchase Request form action not found. Please ensure the Purchase Request module is installed and configured correctly."))

    #     action['views'] = [(self.env.ref('purchase_request.view_purchase_request_form').id, 'form')]
    #     action['res_id'] = purchase_request.id
    #     action['domain'] = [('id', '=', purchase_request.id)]
        
    #     return action

    def action_view_purchase_request(self):
        """Menampilkan Purchase Request terkait"""
        self.ensure_one()
        
        purchase_request = self.purchase_request_id
        if not purchase_request:
            return {'type': 'ir.actions.act_window_close'}

        try:
            # Use the correct XML ID for the Purchase Request action
            action = self.env['ir.actions.actions']._for_xml_id('purchase_request.purchase_request_form_action')
        except ValueError as e:
            _logger.error(f"Failed to load action 'purchase_request.purchase_request_form_action': {e}")
            raise UserError(_("The Purchase Request form action could not be found. Please ensure the Purchase Request module is installed and configured correctly."))

        # Force the form view
        form_view = self.env.ref('purchase_request.view_purchase_request_form')
        action['views'] = [(form_view.id, 'form')]
        action['res_id'] = purchase_request.id
        action['domain'] = [('id', '=', purchase_request.id)]
        
        return action

    def action_pickup(self):
        self.ensure_one()
        ready_picking = self.picking_ids.filtered(lambda p: p.state == 'assigned')
        if ready_picking:
            return self.action_view_stock_picking(pickings=ready_picking)
    
    def action_return(self):
        self.ensure_one()
        ready_picking = self.picking_ids.filtered(lambda p: p.state in ('assigned', 'confirmed'))
        if ready_picking:
            return self.action_view_stock_picking(pickings=ready_picking)
            
    def name_get(self):
        """Override name_get untuk menampilkan info tambahan di list view"""
        result = []
        for record in self:
            name = record.name
            # Tambahkan info singkat setelah nama
            info = []
            if record.purchase_type == 'kapal' and record.vessel_id:
                info.append(record.vessel_id.name[:8])
            elif record.department_id:
                info.append(record.department_id.name[:6])
            
            if info:
                name = f"{name} [{', '.join(info)}]"
            
            result.append((record.id, name))
        return result