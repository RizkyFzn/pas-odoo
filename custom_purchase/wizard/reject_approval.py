# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RejectApproval(models.TransientModel):
    _name = 'reject.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Reject Approval for reason to purchase rejected.'
    _rec_name = 'user_id'

    @api.model
    def _selection_state(self):
        context = self._context
        active_id = context.get('active_id')
        active_model = context.get('active_model')
        purchase_id = self.env[active_model].browse(active_id)
        state = [('approve_manager', 'Approve Manager'), ('sent', 'RFQ Sent'), ('draft', 'RFQ')]
        if purchase_id:
            if purchase_id.state == 'approve_manager':
                state = [('sent', 'RFQ Sent'), ('draft', 'RFQ')]
        return state

    @api.model
    def _default_state(self):
        context = self._context
        active_id = context.get('active_id')
        active_model = context.get('active_model')
        purchase_id = self.env[active_model].browse(active_id)
        default = 'approve_manager'
        if purchase_id:
            if purchase_id.state == 'approve_manager':
                default = 'sent'
        return default

    user_id = fields.Many2one(comodel_name='res.users', string='Rejected By', default=lambda self: self.env.user.id)
    requested_by = fields.Many2one(comodel_name='res.users', string='Rejected To')
    requester = fields.Char(related='requested_by.name', string='Rejected To')
    state = fields.Selection(
        selection=lambda self: self._selection_state(), string='Previous Status',
        required=True, default=lambda self: self._default_state())
    reject_reason = fields.Text(string='Reject Reason', required=True)

    @api.onchange('state')
    def _onchange_state(self):
        context = self._context
        active_model = context.get('active_model')
        if active_model:
            active_id = context.get('active_id')
            purchase_id = self.env[active_model].browse(active_id)
            request_manager_id = purchase_id.requested_manager_by
            request_employee_id = purchase_id.requested_by
            self.requested_by = request_manager_id if self.state == 'approve_manager' else request_employee_id

    def button_confirm(self):
        context = self._context
        active_id = context.get('active_id')
        active_model = context.get('active_model')
        purchase_id = self.env[active_model].browse(active_id)
        # done reject previous activity
        purchase_id._action_done_activity(['bag_purchase.mail_activity_data_reject'])
        # cancel activity message
        purchase_id.activity_unlink([
            'bag_purchase.mail_activity_data_approval_manager',
            'bag_purchase.mail_activity_data_approval_vp'])
        # activity reject message
        purchase_id._user_rejected(
            activity='bag_purchase.mail_activity_data_reject', requester=self.requested_by,
            rejecter=self.user_id, note=self.reject_reason)
        purchase_id.write({
            'state': self.state,
            'is_rejected': True
        })
