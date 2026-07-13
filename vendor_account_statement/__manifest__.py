{
    'name': "vendor_account_statement",

    'summary': """
        Vendor Account Statement in Details""",

    'description': """
        Vendor Account Statement in Details - كشف حساب مورد تفصيلي
    """,

    'author': "Custom",
    'website': "",

    'category': 'Uncategorized',
    'version': '19.0.1.0.0',

    'depends': ['base', 'account', 'product'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/vendor_statement_wizard_views.xml',
        'wizard/vendor_partner_ledger.xml',
    ],
    'demo': [],
    'assets': {
        'web.report_assets_common': [
            '/vendor_account_statement/static/src/less/fonts.css'
        ],
    }
}
