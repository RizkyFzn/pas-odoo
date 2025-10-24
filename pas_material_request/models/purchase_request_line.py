from odoo import fields, models, api

class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    material_request_line_id = fields.Many2one(
        'apm.material.request.line',
        string='Material Request Line',
        readonly=True,
        ondelete='cascade',
        help="Line dari Material Request yang memicu PR line ini"
    )

    last_purchase_price = fields.Monetary(
        string='Last Purchase Price',
        compute='_compute_last_purchase_info',
        store=True,
        currency_field='currency_id',
        help="Harga terakhir kali produk ini dibeli"
    )

    last_purchase_date = fields.Date(
        string='Last Purchase Date',
        compute='_compute_last_purchase_info',
        store=True,
        help="Tanggal terakhir kali produk ini dibeli"
    )

    @api.depends('product_id')
    def _compute_last_purchase_info(self):
        """Compute last purchase price and date from purchase order lines"""
        for line in self:
            if not line.product_id:
                line.last_purchase_price = 0.0
                line.last_purchase_date = False
                continue

            # Search for the last purchase order line for this product
            last_po_line = self.env['purchase.order.line'].search([
                ('product_id', '=', line.product_id.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ], order='date_order desc', limit=1)

            if last_po_line:
                line.last_purchase_price = last_po_line.price_unit
                line.last_purchase_date = last_po_line.date_order.date()
            else:
                line.last_purchase_price = 0.0
                line.last_purchase_date = False