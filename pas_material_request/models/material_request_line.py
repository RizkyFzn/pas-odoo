from datetime import datetime
from collections import defaultdict
import logging

from odoo.exceptions import ValidationError

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class MaterialRequestLine(models.Model):
    _name = 'apm.material.request.line'
    _description = 'Material Request Item'
    _order = 'sequence, id'
    
    
    request_id = fields.Many2one(
        comodel_name='apm.material.request',
        string="Material Request",
        required=True, ondelete='cascade', index=True, copy=False)
    
    sequence = fields.Integer(string="Sequence", default=10)
    
    company_id = fields.Many2one(
        'res.company', 'Company',
        related='request_id.company_id',
        index=True, store=True)
    
    # === FIELD BARU (tanpa engine_id) ===
    engine_type = fields.Selection(
        selection=[
            ('main_engine', 'Main Engine'),
            ('aux_engine', 'Aux Engine'),
            ('generator', 'Generator'),
            ('other', 'Other'),
        ],
        string='Engine Type',
        required=False,
        tracking=True,
        help="Tipe engine untuk material ini"
    )
    
    interval_hour = fields.Float(
        string='Interval Hour',
        digits=(16, 2),
        tracking=True,
        help="Interval pemeliharaan dalam jam (contoh: 500, 1000, 2000)"
    )
    
    last_purchase_date = fields.Date(
        string='Tgl Pembelian Terakhir',
        # compute='_compute_last_purchase_date',
        store=True,
        help="Tanggal pembelian terakhir dari PO untuk produk ini"
    )
    
    for_machine_side = fields.Selection(
        selection=[
            ('kanan', 'Kanan'),
            ('kiri', 'Kiri'),
            ('both', 'Keduanya'),
        ],
        string='For Machine',
        tracking=True,
        help="Sisi mesin: Kanan, Kiri, atau Keduanya"
    )
    # === END FIELD BARU ===
    
    name = fields.Char('Description', compute='_compute_product_name_uom', store=True, readonly=False, required=True, precompute=True)
    product_id = fields.Many2one(
        'product.product', 'Product',
        check_company=True,
        domain="[('type', '=', 'consu'), ('qty_available', '>=', 1)]", index=True, required=True)
    product_uom_qty = fields.Float(
        'Demand',
        digits='Product Unit of Measure',
        default=0, required=True,
        help="This is the quantity to request."
    )
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_uom_id = fields.Many2one(
        'uom.uom', "UoM", required=True, domain="[('category_id', '=', product_uom_category_id)]",
        compute="_compute_product_name_uom", store=True, readonly=False, precompute=True,
    )
    
    move_quantity = fields.Float(string='Quantity', compute='_compute_qty', store=True)
    move_returned = fields.Float(string='Returned Qty', compute='_compute_qty', store=True)

    move_ids = fields.One2many('stock.move', 'material_request_line_id', string='Stock Moves')
    
    forecast_availability = fields.Float('Forecast Availability', compute='_compute_forecast_information', digits='Product Unit of Measure', compute_sudo=True)
    
    # === ONCHANGE METHODS ===
    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     """Compute last_purchase_date saat product_id berubah"""
    #     if self.product_id:
    #         self._compute_last_purchase_date()
    
    # === COMPUTE METHODS ===
    # @api.depends('product_id')
    # def _compute_last_purchase_date(self):
    #     """Ambil tanggal PO terakhir untuk product ini"""
    #     for line in self:
    #         if not line.product_id:
    #             line.last_purchase_date = False
    #             continue
            
    #         last_po_line = self.env['purchase.order.line'].search([
    #             ('product_id', '=', line.product_id.id),
    #             ('order_id.state', 'in', ['purchase', 'done']),
    #         ], order='order_id.date_order desc', limit=1)
            
    #         if last_po_line:
    #             line.last_purchase_date = last_po_line.order_id.date_order.date()
    #         else:
    #             line.last_purchase_date = False
    
    # === VALIDATION ===
    @api.constrains('interval_hour')
    def _check_interval_hour(self):
        """Validasi interval_hour harus positif"""
        for line in self:
            if line.interval_hour and line.interval_hour <= 0:
                raise ValidationError(_("Interval Hour harus lebih besar dari 0"))
    
    # === HELPER METHODS ===
    def _get_line_description(self):
        """Generate description lengkap untuk line ini"""
        self.ensure_one()
        parts = [self.name]
        
        # Tambahkan engine type info
        if self.engine_type:
            engine_type_label = dict(self._fields['engine_type'].selection).get(self.engine_type)
            parts.append(f"[{engine_type_label}]")
        
        # Tambahkan interval
        if self.interval_hour:
            parts.append(f"Int:{self.interval_hour}h")
        
        # Tambahkan machine side
        if self.for_machine_side:
            side_label = dict(self._fields['for_machine_side'].selection).get(self.for_machine_side)
            parts.append(f"Side:{side_label}")
        
        # Tambahkan last purchase date
        if self.last_purchase_date:
            parts.append(f"LastPO:{self.last_purchase_date.strftime('%d/%m/%Y')}")
        
        return ' | '.join(filter(None, parts))
    
    # === END TAMBAHAN ===
    
    @api.depends('product_id')
    def _compute_product_name_uom(self):
        for move in self:
            move.name = move.product_id.name
            move.product_uom_id = move.product_id.uom_id.id

    @api.depends('move_ids.quantity', 'move_ids.state')
    def _compute_qty(self):
        for rec in self:
            qty_delivered = qty_returned = 0
            for move in rec.move_ids.filtered(lambda x: x.state == 'done'):
                if move.picking_id.return_id:
                    qty_returned += move.quantity
                else:
                    qty_delivered += move.quantity
            
            rec.move_quantity = qty_delivered
            rec.move_returned = qty_returned
            
    @api.depends('product_id', 'product_uom_qty', 'request_id.picking_type_id', 'request_id.state', 'request_id.location_id', 'request_id.date_to')
    def _compute_forecast_information(self):
        """ Compute forecasted information of the related product by warehouse."""
        for line in self:
            line.forecast_availability = 0.0  # Default value
        
        # Skip jika tidak ada product
        lines_with_product = self.filtered('product_id')
        if not lines_with_product:
            return
        
        # Set default untuk non-storable products
        not_storable_lines = lines_with_product.filtered(lambda l: not l.product_id.is_storable)
        for line in not_storable_lines:
            line.forecast_availability = line.product_uom_qty
        
        # Hanya process storable products
        storable_lines = lines_with_product - not_storable_lines
        if not storable_lines:
            return
        
        now = fields.Datetime.now()
        
        def safe_key_virtual_available(request, incoming=False):
            """Safe version of key_virtual_available dengan error handling"""
            try:
                # Safety check untuk location_id dan location_dest_id
                source_wh_id = False
                dest_wh_id = False
                
                if request.request_id.location_id:
                    source_wh_id = request.request_id.location_id.warehouse_id.id
                elif request.request_id.request_warehouse_id:
                    source_wh_id = request.request_id.request_warehouse_id.id
                
                if request.request_id.location_dest_id:
                    dest_wh_id = request.request_id.location_dest_id.warehouse_id.id
                elif request.request_id.destination_id:
                    dest_wh_id = request.request_id.destination_id.id
                
                warehouse_id = dest_wh_id if incoming else source_wh_id
                
                # Safety check untuk date_to
                return_date = now
                if request.request_id.date_to:
                    try:
                        return_date = fields.Datetime.from_string(request.request_id.date_to)
                    except:
                        return_date = now
                else:
                    return_date = now
                
                return (warehouse_id or False, return_date)
            except Exception:
                return (False, now)
        
        # Prefetch virtual available
        prefetch_virtual_available = defaultdict(set)
        virtual_available_dict = {}
        
        for line in storable_lines:
            # Skip jika request_id tidak valid
            if not line.request_id:
                continue
                
            # Cek apakah ini consuming (outgoing move)
            is_consuming = line._is_consuming()
            
            if is_consuming and line.request_id.state == 'draft':
                key = safe_key_virtual_available(line)
                prefetch_virtual_available[key].add(line.product_id.id)
            
            # Untuk incoming moves (optional)
            elif line.request_id.picking_type_id and line.request_id.picking_type_id.code == 'incoming':
                key = safe_key_virtual_available(line, incoming=True)
                prefetch_virtual_available[key].add(line.product_id.id)
        
        # Read virtual available untuk semua keys
        for key_context, product_ids in prefetch_virtual_available.items():
            if not product_ids:
                continue
            try:
                warehouse_id, to_date = key_context
                products = self.env['product.product'].browse(list(product_ids))
                if warehouse_id:
                    read_res = products.with_context(
                        warehouse_id=warehouse_id, 
                        to_date=to_date
                    ).read(['virtual_available'])
                else:
                    read_res = products.read(['virtual_available'])
                
                virtual_available_dict[key_context] = {res['id']: res['virtual_available'] or 0.0 for res in read_res}
            except Exception as e:
                _logger.warning(f"Error reading virtual_available for products {product_ids}: {e}")
                virtual_available_dict[key_context] = {pid: 0.0 for pid in product_ids}
        
        # Set forecast availability
        for line in storable_lines:
            if not line.request_id:
                continue
                
            try:
                is_consuming = line._is_consuming()
                
                if is_consuming:
                    key = safe_key_virtual_available(line)
                    virtual_available = virtual_available_dict.get(key, {}).get(line.product_id.id, 0.0)
                    line.forecast_availability = virtual_available - line.product_uom_qty
                else:
                    # Default untuk non-consuming: gunakan current stock
                    line.forecast_availability = line.product_id.with_context(
                        warehouse=line.request_id.request_warehouse_id.id if line.request_id.request_warehouse_id else False
                    ).virtual_available - line.product_uom_qty
                    
            except Exception as e:
                _logger.warning(f"Error computing forecast for line {line.id}: {e}")
                line.forecast_availability = 0.0

    def _prepare_stock_move(self, pick=True):
        self.ensure_one()
        move_vals = {
            'product_id': self.product_id.id,
            'name': self._get_line_description(),
            'product_uom_qty': self.product_uom_qty,
            'material_request_line_id': self.id,
        }
        return move_vals
        
    # def _is_consuming(self):
    #     self.ensure_one()
    #     from_wh = self.request_id.location_id.warehouse_id
    #     to_wh = self.request_id.location_dest_id.warehouse_id
    #     return (from_wh and to_wh and from_wh != to_wh)

    def _is_consuming(self):
        """Check apakah ini consuming move (outgoing dari warehouse)"""
        self.ensure_one()
        
        if not self.request_id:
            return False
        
        # Gunakan warehouse fields langsung (lebih reliable)
        from_wh = self.request_id.request_warehouse_id
        to_wh = self.request_id.destination_id
        
        # Fallback ke location fields jika warehouse kosong
        if not from_wh and self.request_id.location_id:
            from_wh = self.request_id.location_id.warehouse_id
        if not to_wh and self.request_id.location_dest_id:
            to_wh = self.request_id.location_dest_id.warehouse_id
        
        return (from_wh and to_wh and from_wh != to_wh)
    
    def action_product_forecast_report(self):
        self.ensure_one()
        action = self.product_id.action_product_forecast_report()
        action['context'] = {
            'active_id': self.product_id.id,
            'active_model': 'product.product',
            'move_to_match_ids': self.ids,
        }
        if self._is_consuming():
            warehouse = self.request_id.location_id.warehouse_id
        else:
            warehouse = self.request_id.location_dest_id.warehouse_id

        if warehouse:
            action['context']['warehouse_id'] = warehouse.id
        return action

    # @api.onchange('product_uom_qty')
    # def _amount_validation(self):
    #     if self.product_uom_qty > self.product_id.qty_available:
    #         raise ValidationError(
    #             'Quantity On Hand tidak mencukupi Quantity yang akan dipinjam'
    #         )