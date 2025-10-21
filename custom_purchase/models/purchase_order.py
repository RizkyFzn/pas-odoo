from odoo import api, fields, models
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('validate_gm', 'Validate GM Procurement'),
        ('validate_technical', 'Validate Technical'),
        ('approve_mgmt1', 'Approve Management 1'),
        ('approve_mgmt2', 'Approve Management 2'),
        ('approve_mgmt3', 'Approve Management 3'),
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    attachment_teknis = fields.Binary(string='Dokumen Teknis')
    attachment_teknis_filename = fields.Char(string='Attachment Teknis Filename')
    attachment_harga = fields.Binary(string='Dokumen Harga')
    attachment_harga_filename = fields.Char(string='Attachment Harga Filename')
    attachment_administrasi = fields.Binary(string='Dokumen Administrasi')
    attachment_administrasi_filename = fields.Char(string='Attachment Administrasi Filename')
    

    def button_validate_gm(self):
        for order in self:
            if order.supplier_line and not order.has_winner:
                raise UserError('Choose a supplier as the winner first!')
        self.write({'state': 'validate_gm'})

    def button_validate_technical(self):
        self.write({'state': 'validate_technical'})

    def button_approve_mgmt1(self):
        if self.amount_total > 2000000:
            self.write({'state': 'approve_mgmt1'})
        else:
            # _logger.info(f"Amount total is less than 2 million: {self.amount_total}")
            self.button_approve_po()

    def button_approve_mgmt2(self):
        self.write({'state': 'approve_mgmt2'})

    def button_approve_mgmt3(self):
        self.button_approve_po()

    def button_approve_po(self):
        for order in self:
            if order.supplier_line and not order.has_winner:
                raise UserError('Choose a supplier as the winner first!')
            
            # if order.state not in ['draft', 'sent']:
            #     continue
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            # Deal with double validation process
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        return True