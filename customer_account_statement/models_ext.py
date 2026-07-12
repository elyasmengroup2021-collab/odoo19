from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    header_img = fields.Binary(string="Header Image")
    footer_img = fields.Binary(string="Footer Image")


class ProductPaymentLine(models.Model):
    _name = 'product.payment.line'
    _description = 'Product Payment Line'

    payment_id = fields.Many2one('account.payment', string='Payment', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    amount_company_currency = fields.Monetary(string='Amount in Company Currency',
                                              currency_field='company_currency_id')
    currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', store=True)
    company_currency_id = fields.Many2one('res.currency',
                                          related='payment_id.company_id.currency_id', store=True)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    product_payment_ids = fields.One2many('product.payment.line', 'payment_id',
                                          string='Product Payments')
