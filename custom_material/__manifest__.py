# -*- coding: utf-8 -*-
{
    'name': "Material List Custom",

    'summary': "Custom module for Material List",

    'description': """Material List""",

    'author': "Sinergi Tuntas Solusi",
    'website': "https://www.sinergituntassolusi.com",

    'category': 'Sales/Sales',
    'version': '18.0.0.0',
    'depends': ['base', 'product', 'purchase_requisition'],

    'data': [
        # 'security/security.xml',
        'security/ir.model.access.csv',
        
        'data/sequence.xml',

        'views/material_list_views.xml',
        
    ],

    'license': 'OPL-1',

    
}

