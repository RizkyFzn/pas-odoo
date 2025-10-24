from odoo import models, fields, api

class SupplierLineApproval(models.Model):
    _inherit = "supplier.line"

    state = fields.Selection(
        selection=[("winner", "Winner"), ("to_approve", "To Approve"), ("participant", "Participant")],
        string="Status",
        default="participant"
    )

    def action_winner(self):
        # Call the original method but modify the state
        super(SupplierLineApproval, self).action_winner()
        # Override the state to 'to_approve'
        self.write({"state": "to_approve"})

    def action_approve(self):
        self.write({"state": "winner"})