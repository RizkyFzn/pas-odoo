from odoo import models, fields, api

class KapalMaster(models.Model):
    _name = 'kapal.master'
    _description = 'Master Data Kapal'

    name = fields.Char(string='Vessel Name', required=True)
    vessel_code = fields.Char(string='Vessel Code', required=True)
    location_id = fields.Many2one(
        'stock.warehouse', 
        string='Location',
    )
    category = fields.Selection([
        ('barge', 'Barge'),
        ('tugboat', 'Tugboat'),
        ('general', 'General Vessel Cargo'),
    ], string='Category', required=True)
    hour_meter = fields.Char('Hour Meter')
    engine_count = fields.Integer('Engine Count', default=1)
    main_engine = fields.Char('Main Engine')
    aux_engine = fields.Char('Aux Engine')

    destination_id = fields.Many2one(
        comodel_name="stock.warehouse",
        required=True,
        tracking=True,
        index=True,
        string="Destination WH",
        check_company=True,
    )

    sparepart_line_ids = fields.One2many(
        'kapal.master.line', 
        'kapal_master_id',
        string='Sparepart Line'
    )
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.vessel_code})"
            result.append((record.id, name))
        return result