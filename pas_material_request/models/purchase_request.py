from odoo import fields, models

class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    material_request_id = fields.Many2one(
        'apm.material.request',
        string='Material Request',
        readonly=True,
        ondelete='cascade',
        help="Material Request yang memicu Purchase Request ini"
    )