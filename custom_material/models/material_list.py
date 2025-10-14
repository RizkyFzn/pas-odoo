from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MaterialList(models.Model):
    _name = 'material.list'
    _description = 'Material List'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Request Reference",
        required=True, copy=False, readonly=False,
        index='trigram',
        default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_first_approval', 'Waiting First Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    request_by = fields.Many2one('res.users', string='Request By', default=lambda self: self.env.user, required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.today, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    note = fields.Text(string='Note')
    attachment = fields.Binary(string='Attachment')
    attachment_filename = fields.Char(string='Attachment Filename')
    request_from_id = fields.Many2one('stock.warehouse', string='Request From')
    product_line_ids = fields.One2many('material.list.line', 'request_id', string='Product Lines')

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            sequence = self.env['ir.sequence'].next_by_code('material.list')
            if not sequence:
                raise UserError("Gagal menghasilkan nomor sequence untuk Material List. Pastikan sequence 'material.list' dikonfigurasi dengan benar.")
            vals['name'] = sequence
        return super(MaterialList, self).create(vals)
    
    def action_submit_for_approval(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Hanya dokumen dalam status Draft yang dapat dikirim untuk approval.")
        self.write({'state': 'waiting_first_approval'})

    def action_first_approve(self):
        self.ensure_one()
        if self.state != 'waiting_first_approval':
            raise UserError("Hanya dokumen dalam status Waiting First Approval yang dapat disetujui pada tahap pertama.")
        self.write({'state': 'approved'})
        return self.action_create_purchase_request()

    def action_reject(self):
        self.ensure_one()
        if self.state not in ['waiting_first_approval', 'waiting_second_approval']:
            raise UserError("Hanya dokumen dalam status Waiting Approval yang dapat ditolak.")
        self.write({'state': 'rejected'})

    def action_create_purchase_request(self):
        self.ensure_one()
        if not self.product_line_ids:
            raise UserError("Tidak ada product lines untuk membuat Purchase Request.")

        purchase_request_vals = {
            'name': f"PR/{self.name}",
            'requested_by': self.request_by.id,
            'date_start': self.request_date,
            'company_id': self.company_id.id,
            'description': self.note or '',
            'line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or '',
                'product_qty': line.quantity_needed,
                'product_uom_id': line.uom_id.id,
            }) for line in self.product_line_ids],
        }

        purchase_request = self.env['purchase.request'].create(purchase_request_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': purchase_request.id,
            'target': 'current',
        }