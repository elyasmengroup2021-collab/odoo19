from collections import defaultdict
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CustomerBatch(models.Model):
    _name = 'customer.batch'
    _description = 'Customer Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Batch Number',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
        tracking=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    duration_days = fields.Integer(
        string='Duration (Days)',
        required=True,
        default=1,
        tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True,
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('discount_applied', 'Discount Applied'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    open_batch_key = fields.Char(
        compute='_compute_open_batch_key',
        store=True,
        index=True,
        copy=False,
    )
    invoice_ids = fields.One2many(
        'account.move',
        'batch_id',
        string='Invoices',
        readonly=True,
    )
    consumption_line_ids = fields.One2many(
        'customer.batch.line',
        'batch_id',
        string='Consumption Lines',
        copy=False,
    )
    total_quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_totals',
        store=True,
        digits='Product Unit',
    )
    discount_per_unit = fields.Monetary(
        string='Discount / UoM',
        currency_field='currency_id',
        copy=False,
        tracking=True,
        help='One uniform discount rate applied to the total consumption of all products in this batch.',
    )
    total_discount = fields.Monetary(
        string='Total Discount',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    discount_move_id = fields.Many2one(
        'account.move',
        string='Discount Journal Entry',
        readonly=True,
        copy=False,
        tracking=True,
    )
    discount_date = fields.Date(
        string='Discount Date',
        readonly=True,
        copy=False,
        tracking=True,
    )
    discount_account_id = fields.Many2one(
        'account.account',
        string='Discount Account Used',
        readonly=True,
        copy=False,
    )
    discount_journal_id = fields.Many2one(
        'account.journal',
        string='Discount Journal Used',
        readonly=True,
        copy=False,
    )
    configured_discount_account_id = fields.Many2one(
        'account.account',
        string='Configured Discount Account',
        related='company_id.customer_batch_discount_account_id',
        readonly=True,
    )
    configured_discount_journal_id = fields.Many2one(
        'account.journal',
        string='Configured Discount Journal',
        related='company_id.customer_batch_discount_journal_id',
        readonly=True,
    )
    discount_label = fields.Char(
        string='Discount Label / Note',
        copy=False,
        tracking=True,
        help='Optional label copied to the discount journal entry reference and lines.',
    )
    discount_move_ref = fields.Char(
        string='Applied Entry Reference',
        related='discount_move_id.ref',
        readonly=True,
    )
    notes = fields.Html(string='Notes')

    _sql_constraints = [
        (
            'customer_batch_name_unique',
            'unique(name)',
            'The batch number must be unique.',
        ),
        (
            'one_open_batch_per_customer_company',
            'unique(partner_id, company_id, open_batch_key)',
            'A customer can have only one open batch per company.',
        ),
    ]

    @api.depends('start_date', 'duration_days')
    def _compute_end_date(self):
        for batch in self:
            if batch.start_date and batch.duration_days > 0:
                batch.end_date = batch.start_date + timedelta(
                    days=batch.duration_days - 1
                )
            else:
                batch.end_date = False

    @api.depends('state')
    def _compute_open_batch_key(self):
        for batch in self:
            batch.open_batch_key = 'open' if batch.state == 'open' else False

    @api.depends(
        'discount_per_unit',
        'consumption_line_ids.quantity',
        'consumption_line_ids.discount_amount',
        'consumption_line_ids.batch_id.discount_per_unit',
    )
    def _compute_totals(self):
        for batch in self:
            batch.total_quantity = sum(batch.consumption_line_ids.mapped('quantity'))
            batch.total_discount = sum(
                batch.currency_id.round(line.quantity * batch.discount_per_unit)
                for line in batch.consumption_line_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = sequence.next_by_code('customer.batch.sequence') or '/'
        return super().create(vals_list)

    @api.constrains('duration_days', 'start_date', 'end_date')
    def _check_dates(self):
        for batch in self:
            if batch.duration_days <= 0:
                raise ValidationError(_('Duration must be greater than zero.'))
            if batch.start_date and batch.end_date and batch.end_date < batch.start_date:
                raise ValidationError(_('The end date cannot be before the start date.'))

    def _ensure_no_open_batch_conflict(self):
        for batch in self:
            if not batch.partner_id or not batch.company_id:
                continue
            commercial_partner = batch.partner_id.commercial_partner_id
            duplicate = self.search([
                ('id', '!=', batch.id),
                ('company_id', '=', batch.company_id.id),
                ('state', '=', 'open'),
                ('partner_id.commercial_partner_id', '=', commercial_partner.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Customer %(customer)s already has an open batch: %(batch)s. '
                    'Close or cancel it before opening a new batch.',
                    customer=commercial_partner.display_name,
                    batch=duplicate.display_name,
                ))

    @api.constrains('partner_id', 'company_id', 'state')
    def _check_one_open_batch_per_commercial_customer(self):
        self.filtered(lambda batch: batch.state == 'open')._ensure_no_open_batch_conflict()

    @api.constrains('partner_id', 'company_id')
    def _check_partner_company(self):
        for batch in self:
            if batch.partner_id and batch.company_id:
                commercial_company = batch.partner_id.commercial_partner_id
                if commercial_company.company_id and commercial_company.company_id != batch.company_id:
                    raise ValidationError(
                        _('The customer is restricted to another company.')
                    )

    def _check_editable(self):
        self.ensure_one()
        if self.state in ('closed', 'discount_applied', 'cancelled'):
            raise UserError(_('This batch is no longer editable in its current state.'))

    def action_open(self):
        for batch in self:
            if batch.state != 'draft':
                raise UserError(_('Only draft batches can be opened.'))
            batch._check_dates()
            batch._ensure_no_open_batch_conflict()
            batch.state = 'open'
        return True

    def action_close(self):
        for batch in self:
            if batch.state != 'open':
                raise UserError(_('Only open batches can be closed.'))
            batch.state = 'closed'
        return True

    def action_cancel(self):
        for batch in self:
            if batch.state == 'discount_applied':
                raise UserError(_('A batch with an applied discount cannot be cancelled.'))
            if batch.discount_move_id:
                raise UserError(_('Reverse the discount entry instead of cancelling this batch.'))
            batch.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group('customer_batch_discount.group_customer_batch_reset'):
            raise UserError(_('You do not have permission to reset a cancelled batch to draft.'))
        for batch in self:
            if batch.state != 'cancelled':
                raise UserError(_('Only cancelled batches can be reset to draft.'))
            if batch.discount_move_id:
                raise UserError(
                    _('A batch linked to a discount journal entry cannot be reset to draft.')
                )
            batch.write({'state': 'draft'})
            batch.message_post(
                body=_('Batch reset to Draft by %(user)s.', user=self.env.user.display_name)
            )
        return True

    def action_calculate_consumption(self):
        for batch in self:
            if batch.state != 'closed':
                raise UserError(_('Close the batch before calculating consumption.'))
            batch._rebuild_consumption_lines()
        return True

    def action_open_discount_wizard(self):
        self.ensure_one()
        if self.state != 'closed':
            raise UserError(_('Discount can only be applied to a closed batch.'))
        if not self.consumption_line_ids:
            raise UserError(_('No consumption found for this batch.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Apply Customer Batch Discount'),
            'res_model': 'customer.batch.discount.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_id': self.id},
        }

    def _get_consumption_invoice_lines(self):
        self.ensure_one()
        if self.company_id.customer_batch_consumption_source != 'invoices':
            raise UserError(
                _('Only posted customer invoices are implemented as a consumption source in this release.')
            )
        moves = self.env['account.move'].search([
            ('batch_id', '=', self.id),
            ('company_id', '=', self.company_id.id),
            ('commercial_partner_id', '=', self.partner_id.commercial_partner_id.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date),
        ])
        return moves.mapped('invoice_line_ids').filtered(
            lambda line: line.product_id and line.display_type == 'product'
        )

    def action_apply_discount_from_lines(self):
        for batch in self:
            if batch.state != 'closed':
                raise UserError(_('Discount can only be applied to a closed batch.'))
            if not batch.consumption_line_ids:
                raise UserError(_('No consumption found for this batch.'))
            if batch.discount_per_unit <= 0:
                raise UserError(_('Enter a positive uniform Discount / UoM rate before applying the discount.'))
            batch.apply_discount(batch.discount_per_unit)
        return True

    def _rebuild_consumption_lines(self):
        self.ensure_one()
        grouped = defaultdict(lambda: {
            'quantity': 0.0,
            'invoice_ids': set(),
            'sales_amount': 0.0,
            'uom_id': False,
        })
        batch_lines = self._get_consumption_invoice_lines()
        for invoice_line in batch_lines:
            invoice = invoice_line.move_id
            product = invoice_line.product_id
            source_uom = invoice_line.product_uom_id or product.uom_id
            configured_uom = self.company_id.customer_batch_discount_uom_id
            target_uom = (
                configured_uom
                if configured_uom and configured_uom._has_common_reference(source_uom)
                else product.uom_id
            )
            quantity = source_uom._compute_quantity(
                invoice_line.quantity,
                target_uom,
                round=False,
            )
            sign = -1.0 if invoice.move_type == 'out_refund' else 1.0
            currency = invoice.currency_id or self.currency_id
            sales_amount = currency._convert(
                invoice_line.price_subtotal,
                self.currency_id,
                self.company_id,
                invoice.invoice_date or invoice.date,
            )
            data = grouped[product.id]
            data['quantity'] += sign * quantity
            data['invoice_ids'].add(invoice.id)
            data['sales_amount'] += sign * sales_amount
            data['uom_id'] = target_uom.id

        self.consumption_line_ids.unlink()
        vals_list = []
        for product_id, data in grouped.items():
            target_uom = self.env['uom.uom'].browse(data['uom_id'])
            if target_uom.is_zero(data['quantity']):
                continue
            vals_list.append({
                'batch_id': self.id,
                'product_id': product_id,
                'quantity': data['quantity'],
                'uom_id': data['uom_id'],
                'invoice_count': len(data['invoice_ids']),
                'total_sales_amount': data['sales_amount'],
            })
        if vals_list:
            self.env['customer.batch.line'].create(vals_list)
        self.message_post(body=_('Consumption was calculated from posted customer invoices.'))
        return True

    def apply_discount(self, discount_values):
        self.ensure_one()
        if self.state != 'closed':
            raise UserError(_('Discount can only be applied to a closed batch.'))
        if self.discount_move_id or self.state == 'discount_applied':
            raise UserError(_('This batch discount has already been applied.'))
        if not self.consumption_line_ids:
            raise UserError(_('No consumption found for this batch.'))

        company = self.company_id
        discount_account = company.customer_batch_discount_account_id
        discount_journal = company.customer_batch_discount_journal_id
        if not discount_account:
            raise UserError(
                _('Please configure the Customer Batch Discount Account before applying the discount.')
            )
        if not discount_journal:
            raise UserError(
                _('Please configure the Customer Batch Discount Journal before applying the discount.')
            )
        if company not in discount_account.company_ids or discount_journal.company_id != company:
            raise UserError(_('The discount account and journal must belong to the batch company.'))

        if isinstance(discount_values, dict):
            rates = {self.currency_id.round(rate or 0.0) for rate in discount_values.values()}
            if len(rates) > 1:
                raise ValidationError(_('Only one uniform discount rate is allowed for the whole batch.'))
            rate = next(iter(rates), 0.0)
        else:
            rate = discount_values or 0.0
        if rate < 0:
            raise ValidationError(_('Discount values cannot be negative.'))

        self.discount_per_unit = rate
        total_discount = 0.0
        for line in self.consumption_line_ids:
            amount = self.currency_id.round(line.quantity * rate)
            if line.quantity < 0 and not self.currency_id.is_zero(amount):
                raise ValidationError(
                    _('A product with net negative consumption cannot receive a discount.')
                )
            line.with_context(batch_discount_apply=True).write({'discount_per_unit': rate})
            total_discount += amount

        total_discount = self.currency_id.round(total_discount)
        if total_discount <= 0:
            raise UserError(_('The total discount must be greater than zero.'))

        receivable = self.partner_id.with_company(company).property_account_receivable_id
        if not receivable or receivable.account_type != 'asset_receivable':
            raise UserError(_('The customer does not have a valid receivable account.'))

        discount_date = fields.Date.context_today(self)
        reference = self.discount_label.strip() if self.discount_label else ''
        reference = reference or _('Customer Batch Discount - %s', self.name)

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': discount_date,
            'journal_id': discount_journal.id,
            'ref': reference,
            'line_ids': [
                Command.create({
                    'name': reference,
                    'account_id': receivable.id,
                    'partner_id': self.partner_id.id,
                    'debit': total_discount,
                    'credit': 0.0,
                }),
                Command.create({
                    'name': reference,
                    'account_id': discount_account.id,
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': total_discount,
                }),
            ],
        })
        move.action_post()
        self.write({
            'discount_move_id': move.id,
            'discount_date': discount_date,
            'discount_account_id': discount_account.id,
            'discount_journal_id': discount_journal.id,
            'state': 'discount_applied',
        })
        self.message_post(body=_(
            'Customer Batch Discount Applied<br/>'
            'Batch: %(batch)s<br/>'
            'Customer: %(customer)s<br/>'
            'Total Quantity: %(quantity)s<br/>'
            'Total Discount: %(discount)s<br/>'
            'Journal Entry: %(move)s',
            batch=self.name,
            customer=self.partner_id.display_name,
            quantity=self.total_quantity,
            discount=self.total_discount,
            move=move.display_name,
        ))
        return move

    def action_view_discount_move(self):
        self.ensure_one()
        if not self.discount_move_id:
            raise UserError(_('No discount journal entry exists for this batch.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discount Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.discount_move_id.id,
        }


class CustomerBatchLine(models.Model):
    _name = 'customer.batch.line'
    _description = 'Customer Batch Consumption Line'
    _order = 'product_id, id'

    batch_id = fields.Many2one(
        'customer.batch',
        string='Batch',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='restrict',
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        digits='Product Unit',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        required=True,
        ondelete='restrict',
    )
    invoice_count = fields.Integer(string='Invoice Count', readonly=True)
    total_sales_amount = fields.Monetary(
        string='Total Sales Amount',
        currency_field='currency_id',
        readonly=True,
    )
    discount_per_unit = fields.Monetary(
        string='Discount / UoM',
        currency_field='currency_id',
        copy=False,
    )
    discount_amount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_discount_amount',
        store=True,
        currency_field='currency_id',
        copy=False,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='batch_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('quantity', 'discount_per_unit', 'batch_id.discount_per_unit', 'currency_id')
    def _compute_discount_amount(self):
        for line in self:
            rate = line.batch_id.discount_per_unit or line.discount_per_unit
            line.discount_amount = (
                line.currency_id.round(line.quantity * rate)
                if line.currency_id else 0.0
            )

    def write(self, vals):
        if 'discount_per_unit' in vals:
            if not self.env.context.get('batch_discount_apply'):
                raise UserError(
                    _('Set one uniform Discount / UoM rate on the batch instead of editing products individually.')
                )
            for line in self:
                if line.batch_id.state != 'closed':
                    raise UserError(
                        _('Discount rates can only be applied while the batch is closed.')
                    )
        return super().write(vals)

    @api.constrains('quantity', 'discount_per_unit', 'discount_amount')
    def _check_non_negative_discount(self):
        for line in self:
            if line.discount_per_unit < 0 or line.discount_amount < 0:
                raise ValidationError(_('Discount values cannot be negative.'))
