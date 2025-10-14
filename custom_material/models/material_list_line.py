from odoo import models, fields, api
from odoo.exceptions import UserError

class MaterialListLine(models.Model):
    _name = 'material.list.line'
    _description = 'Material List Line'

    request_id = fields.Many2one('material.list', string='Material List', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Part Number', required=True, domain="[('purchase_ok', '=', True)]")
    description = fields.Text(string='Description')
    quantity_needed = fields.Float(string='Quantity Needed', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, default=lambda self: self.env['uom.uom'].search([('id', '=', 1)], limit=1))
    priority_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Priority Level', default='medium', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(MaterialListLine, self).default_get(fields_list)
        if 'request_id' in fields_list and not res.get('request_id'):
            res['request_id'] = self.env.context.get('default_request_id')
        return res

    @api.onchange('product_id', 'quantity_needed')
    def _onchange_check_uom(self):
        if not self.uom_id:
            self.uom_id = self.env['uom.uom'].search([('id', '=', 1)], limit=1)
            if not self.uom_id:
                raise UserError("Satuan ukur default tidak ditemukan. Harap pilih Unit of Measure.")