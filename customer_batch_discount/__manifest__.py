{
    'name': 'Customer Batch Discount',
    'version': '19.0.1.0.10',
    'summary': 'Customer batch consumption and discount accounting',
    'description': """
Customer Batch Discount
=======================

Manages customer business cycles, posted-invoice consumption, customer
 discounts, and one balanced accounting entry per completed batch.
    """,
    'author': 'Manus AI',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'mail', 'uom'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/customer_batch_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'wizard/batch_discount_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
}
