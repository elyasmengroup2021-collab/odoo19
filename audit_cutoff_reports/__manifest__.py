{
 'name':'Audit Cut-off Reports',
 'version':'19.0.17.0.0',
 'category':'Accounting/Accounting',
 'summary':'Native Odoo 19 list/search cut-off review reports',
 'author':'Custom',
 'license':'LGPL-3',
 'depends':['account','om_account_accountant','purchase','purchase_stock','sale','sale_stock'],
 'data':['security/ir.model.access.csv','views/cutoff_views.xml','views/menu.xml'],
 'assets':{'web.assets_backend':[
   'audit_cutoff_reports/static/src/js/cutoff_bootstrap.js',
   'audit_cutoff_reports/static/src/js/cutoff_list.js',
   'audit_cutoff_reports/static/src/xml/cutoff_list.xml',
   'audit_cutoff_reports/static/src/scss/cutoff_list.scss',
 ]},
 'installable':True,'application':False,
}
