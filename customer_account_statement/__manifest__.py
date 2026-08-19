{
    'name': "Customer Account Statement",

    'summary': """
        Customer Account Statement in Details""",

    'description': """
        Customer Account Statement in Details
    """,

    'author': "Trio M Smart Solutions",
    'website': "",

    'category': 'Accounting',
    'version': '19.0.1.0.2',

    'depends': ['base', 'account', 'product'],

    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'wizard/customer_statement_wizard_views.xml',
        'wizard/partner_ledger.xml',
    ],

    'assets': {
        'web.report_assets_common': [
            '/customer_account_statement/static/src/less/fonts.css'
        ],
    },

    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
