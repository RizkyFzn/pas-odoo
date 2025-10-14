# -*- coding: utf-8 -*-
{
    'name': "pas_purchase",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['purchase_requisition', 'purchase_request'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',

        'views/purchase_order_views.xml',
        
    ],
}
