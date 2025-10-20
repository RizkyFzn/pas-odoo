from odoo import models, fields, api

class KapalMasterLine(models.Model):
    _name = 'kapal.master.line'
    _description = 'Master Data Kapal Line'
    _rec_name = 'product_id'

    kapal_master_id = fields.Many2one(
        'kapal.master', 
        string='Ship Master', 
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.template', 
        string='Product/PN',
        required=False,  # ✅ FIXED: True → False
    )
    
    category_pn = fields.Char(
        string='Category PN', 
        compute='_compute_category_pn',  # ✅ UNCOMMENT
        store=True
    )
    
    serial_number_id = fields.Many2one(
        'stock.lot', 
        string='Serial Number',
        required=False,  # ✅ ADD
    )

    
    engine_type = fields.Selection([
        ('main_engine', 'Main Engine'),
        ('aux_engine', 'Auxiliary Engine'),
        ('engine_support', 'Engine Support Item')
    ], string='Engine Type', required=True)
    
    installation_date = fields.Datetime(string='Installation Date')
    hour_meter_install = fields.Float(string='Hour Meter at Install')
    last_replacement_date = fields.Date(string='Last Replacement Date')
    note = fields.Text(string='Note')
    status = fields.Selection([  # ✅ UNCOMMENT
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('replaced', 'Replaced')
    ], string='Status', default='active')
    
    @api.depends('product_id')  # ✅ UNCOMMENT
    def _compute_category_pn(self):
        for line in self:
            if line.product_id and line.product_id.categ_id:
                line.category_pn = line.product_id.categ_id.name or ''
            else:
                line.category_pn = ''
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            return {
                'domain': {
                    'serial_number_id': [
                        ('product_id.product_tmpl_id', '=', self.product_id.id)
                    ]
                }
            }
        self.serial_number_id = False