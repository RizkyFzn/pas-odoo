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

    attachment_teknis = fields.Binary(string='Dokumen Teknis')
    attachment_teknis_filename = fields.Char(string='Attachment Teknis Filename')
    attachment_harga = fields.Binary(string='Dokumen Harga')
    attachment_harga_filename = fields.Char(string='Attachment Harga Filename')
    attachment_administrasi = fields.Binary(string='Dokumen Administrasi')
    attachment_administrasi_filename = fields.Char(string='Attachment Administrasi Filename')
    

    def button_validate_gm(self):
        self.write({'state': 'validate_gm'})

    def button_validate_technical(self):
        self.write({'state': 'validate_technical'})

    def button_approve_mgmt1(self):
        if self.amount_total > 2000000:
            self.write({'state': 'approve_mgmt1'})
        else:
            self.button_approve()

    def button_approve_mgmt2(self):
        self.write({'state': 'approve_mgmt2'})

    def button_approve_mgmt3(self):
        self.button_approve()

    def button_approve(self):
        super(PurchaseOrder, self).button_confirm()