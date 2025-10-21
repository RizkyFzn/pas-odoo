from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'
    
    material_request_line_id = fields.Many2one('apm.material.request.line', 'Material Request Line', index='btree_not_null')
    
    shipment_condition = fields.Integer(compute='_check_full_shipment')
    
    @api.depends('product_uom_qty', 'quantity')
    def _check_full_shipment(self):
        for move in self:
            if not(move.product_uom_qty and move.quantity):
                move.shipment_condition = 0
            elif move.product_uom_qty == move.quantity:
                move.shipment_condition = 1
            else:
                move.shipment_condition = -1
                
    def _get_src_account(self, accounts_data):
        if self.material_request_line_id.request_id.request_type == 'inventory':
            return accounts_data['expense'].id
        
        return super()._get_src_account(accounts_data)

    def _get_dest_account(self, accounts_data):
        if self.material_request_line_id.request_id.request_type == 'inventory':
            return accounts_data['expense'].id
        
        return super()._get_dest_account(accounts_data)