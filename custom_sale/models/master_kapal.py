from odoo import models, fields, api
from odoo.exceptions import UserError

class KapalMaster(models.Model):
    _name = 'kapal.master'
    _description = 'Master Data Kapal'

    name = fields.Char(string='Vessel Name', required=True)
    vessel_code = fields.Char(string='Vessel Code', required=True)
    location_id = fields.Many2one(
        'stock.location',
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

    def action_generate_location(self):
        """Generate stock location from vessel_code + '/' + vessel name"""
        for record in self:
            if not record.destination_id:
                raise UserError("Destination warehouse harus diisi terlebih dahulu.")

            if not record.name:
                raise UserError("Vessel name harus diisi terlebih dahulu.")

            if not record.vessel_code:
                raise UserError("Vessel code harus diisi terlebih dahulu.")

            # Generate location name
            vessel_name = record.name.strip()
            location_name = f"{vessel_name}"

            # Check if location already exists
            existing_location = self.env['stock.location'].search([
                ('name', '=', location_name),
                ('company_id', '=', record.destination_id.company_id.id)
            ], limit=1)

            if existing_location:
                # Update existing location
                record.location_id = existing_location.id
                # Commit to ensure the field is saved
                self.env.cr.commit()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Location Already Exists',
                        'message': f'Location dengan nama {location_name} sudah ada. Location telah diupdate.',
                        'type': 'info',
                        'sticky': False,
                    }
                }

            try:
                new_location = self.env['stock.location'].create({
                    'name': location_name,
                    'usage': 'internal',
                    'company_id': record.destination_id.company_id.id,
                    'location_id': record.destination_id.view_location_id.id,
                })

                record.location_id = new_location.id

                # return {
                #     'type': 'ir.actions.client',
                #     'tag': 'display_notification',
                #     'params': {
                #         'title': 'Location Created',
                #         'message': f'Stock location dengan nama {location_name} berhasil dibuat.',
                #         'type': 'success',
                #         'sticky': False,
                #     }
                # }

            except Exception as e:
                raise UserError(f"Gagal membuat stock location: {str(e)}")
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.vessel_code})"
            result.append((record.id, name))
        return result