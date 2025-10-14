from odoo import api, fields, models
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('validate_gm', 'Validate GM Procurement'),
        ('validate_technical', 'Validate Technical'),
        ('approve_mgmt1', 'Approve Management 1'),
        ('approve_mgmt2', 'Approve Management 2'),
        ('approve_mgmt3', 'Approve Management 3'),
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    def button_validate_gm(self):
        self.write({'state': 'validate_technical'})

    def button_validate_technical(self):
        self.write({'state': 'approve_mgmt1'})

    def button_approve_mgmt1(self):
        if self.amount_total > 2000000:
            self.write({'state': 'approve_mgmt2'})
        else:
            self.write({'state': 'purchase'})

    def button_approve_mgmt2(self):
        self.write({'state': 'approve_mgmt3'})

    def button_approve_mgmt3(self):
        self.write({'state': 'purchase'})

    def button_approve(self):
        super(PurchaseOrder, self).button_approve()