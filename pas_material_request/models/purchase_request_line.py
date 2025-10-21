from odoo import fields, models

class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    material_request_line_id = fields.Many2one(
        'apm.material.request.line',
        string='Material Request Line',
        readonly=True,
        ondelete='cascade',
        help="Line dari Material Request yang memicu PR line ini"
    )