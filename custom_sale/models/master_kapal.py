from odoo import models, fields

class KapalMaster(models.Model):
    _name = 'kapal.master'
    _description = 'Master Data Kapal'

    vessel_code = fields.Char(string='Vessel Code', required=True)
    name = fields.Char(string='Vessel Name', required=True)
    type = fields.Selection([
        ('barge', 'Barge'),
        ('tugboat', 'Tugboat'),
        ('mother', 'Mother Vessel'),
        ('crane', 'Floating Crane'),
    ], string='Type')
    capacity = fields.Float('Capacity (MT)')
    status = fields.Selection([
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('maintenance', 'Maintenance'),
        ('out', 'Out of Service'),
    ], string='Status')
    next_available_date = fields.Date('Next Available Date')
    pic_id = fields.Many2one('res.partner', string='PIC')
