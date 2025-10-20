# -*- coding: utf-8 -*-
{
    'name': "Sale Custom",

    'summary': "Custom module for Sale",

    'description': """Master Data""",

    'author': "Sinergi Tuntas Solusi",
    'website': "https://www.sinergituntassolusi.com",

    'category': 'Sales/Sales',
    'version': '18.0.0.0',
    'depends': ['base', 'stock'],

    'data': [
        # 'security/security.xml',
        'security/ir.model.access.csv',
        

        'views/master_kapal_views.xml',
        
    ],

    'license': 'OPL-1',

    
}

