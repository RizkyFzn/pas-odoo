from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    
    mr_count = fields.Integer(string="Material Request Count", compute='_get_material_request')
    mr_ids = fields.Many2many(
        comodel_name='apm.material.request',
        string="Material Request",
        compute='_get_material_request',
        search='_search_mr_ids',
        copy=False)
    
    return_date = fields.Date(
        string="Return Date",
        help="Date for schedule.",
        default=fields.Date.context_today,
        tracking=True,
        required=True,
    )
    
    
    shipment_condition = fields.Integer(compute='_check_full_shipment')
    
    @api.depends('move_ids_without_package.shipment_condition')
    def _check_full_shipment(self):
        for rec in self:
            shipment_condition = rec.move_ids_without_package.mapped('shipment_condition')
            if -1 in shipment_condition:
                rec.shipment_condition = -1
            elif 0 in shipment_condition:
                rec.shipment_condition = 0
            else:
                rec.shipment_condition = 1
    
    @api.depends('move_ids_without_package.material_request_line_id')
    def _get_material_request(self):
        for picking in self:
            material_request = picking.move_ids_without_package.mapped('material_request_line_id.request_id')
            picking.mr_ids = material_request
            picking.mr_count = len(material_request)
            
    def _search_mr_ids(self, operator, value):
        return [('move_ids_without_package.material_request_line_id', operator, value)]

    def action_view_material_request(self):
        mrs = self.mapped('mr_ids')
        action = self.env['ir.actions.actions']._for_xml_id('apm_material_request.material_request_form_action')
        if len(mrs) > 1:
            action['domain'] = [('id', 'in', mrs.ids)]
        elif len(mrs) == 1:
            form_view = [(self.env.ref('apm_material_request.view_material_request_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = mrs.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action