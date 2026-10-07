from odoo import fields, models


class AccountCutoffFavorite(models.Model):
    _name = 'account.cutoff.favorite'
    _description = 'Audit Cut-off Favorite Search'
    _order = 'is_default desc, name asc'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', required=True, index=True, default=lambda self: self.env.user)
    report_type = fields.Selection([
        ('bills_to_receive', 'Bills To Receive'),
        ('billed_not_received', 'Billed Not Received'),
        ('invoices_to_issue', 'Invoices To Be Issued'),
        ('invoiced_not_delivered', 'Invoiced Not Delivered'),
    ], required=True, index=True)
    search = fields.Char()
    partner_id = fields.Many2one('res.partner')
    product_id = fields.Many2one('product.product')
    last365 = fields.Boolean(default=True)
    group_by = fields.Selection([
        ('partner', 'Vendor/Customer'),
        ('product', 'Product'),
        ('order', 'Order Reference'),
        ('salesperson', 'Salesperson'),
        ('uom', 'Unit'),
        ('none', 'None'),
    ], default='partner')
    is_default = fields.Boolean(default=False)
