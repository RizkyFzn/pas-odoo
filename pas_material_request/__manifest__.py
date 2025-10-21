# -*- coding: utf-8 -*-
{
    'name': "Material Request",

    'summary': """Material request to Internal Transfer""",

    'author': "Adhigana Perkasa Mandiri",
    'website': "http://www.adhiganacorp.com",

    'category': 'Inventory/Purchase',
    'version': '18.0.0.0',

    'depends': ['stock_account','custom_sale','stock', 'purchase_request'],

    'data': [
        'security/group_material_request.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/sequence_data.xml',
        'views/material_request_views.xml',
        'views/stock_picking_views.xml',
    ],
    
    'license': 'OPL-1'

}
