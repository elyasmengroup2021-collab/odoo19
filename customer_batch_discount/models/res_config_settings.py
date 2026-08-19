from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    customer_batch_discount_account_id = fields.Many2one(
        'account.account',
        string='Customer Batch Discount Account',
        domain="[('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable', 'liability_payable')), ('company_ids', 'in', company_id)]",
        check_company=True,
        help='Credit account used for the standalone customer-batch discount entry.',
    )
    customer_batch_discount_journal_id = fields.Many2one(
        'account.journal',
        string='Customer Batch Discount Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        check_company=True,
        help='Journal used for the standalone customer-batch discount entry.',
    )
    customer_batch_consumption_source = fields.Selection(
        [('invoices', 'Posted Customer Invoices')],
        string='Consumption Source',
        default='invoices',
        required=True,
    )
    customer_batch_discount_uom_id = fields.Many2one(
        'uom.uom',
        string='Default Discount UoM',
        help='Optional target UoM used to normalize consumption quantities, such as TON.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    customer_batch_discount_account_id = fields.Many2one(
        related='company_id.customer_batch_discount_account_id',
        readonly=False,
    )
    customer_batch_discount_journal_id = fields.Many2one(
        related='company_id.customer_batch_discount_journal_id',
        readonly=False,
    )
    customer_batch_consumption_source = fields.Selection(
        related='company_id.customer_batch_consumption_source',
        readonly=False,
    )
    customer_batch_discount_uom_id = fields.Many2one(
        related='company_id.customer_batch_discount_uom_id',
        readonly=False,
    )
