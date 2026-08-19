from odoo import _, api, fields, models
from odoo.tools import frozendict
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    batch_id = fields.Many2one(
        'customer.batch',
        string='Customer Batch',
        index=True,
        check_company=True,
        copy=False,
        domain="[('partner_id', '=', commercial_partner_id), ('company_id', '=', company_id), ('state', '=', 'open')]",
    )
    batch_end_date = fields.Date(
        string='Batch End Date',
        related='batch_id.end_date',
        readonly=True,
    )

    @api.constrains('batch_id', 'partner_id', 'company_id', 'move_type', 'invoice_payment_term_id')
    def _check_batch_link(self):
        for move in self:
            if not move.batch_id:
                continue
            if move.move_type not in ('out_invoice', 'out_refund'):
                raise ValidationError(_('Only customer invoices and credit notes can be linked to a batch.'))
            if move.partner_id.commercial_partner_id != move.batch_id.partner_id.commercial_partner_id:
                raise ValidationError(_('The invoice customer must match the batch customer.'))
            if move.company_id != move.batch_id.company_id:
                raise ValidationError(_('The invoice and batch must belong to the same company.'))
            if move.batch_id.state != 'open':
                raise ValidationError(_('An invoice can only be linked to an open batch.'))
            if move.invoice_payment_term_id and move.invoice_payment_term_id.line_ids.filtered(
                lambda line: line.delay_type == 'batch_end_date'
            ) and not move.batch_id.end_date:
                raise ValidationError(_('The linked batch must have a valid end date.'))
        for move in self:
            if (
                not move.batch_id
                and move.invoice_payment_term_id
                and move.invoice_payment_term_id.line_ids.filtered(
                    lambda line: line.delay_type == 'batch_end_date'
                )
            ):
                raise ValidationError(
                    _('The Batch End Date payment-term option requires a linked customer batch.')
                )

    def _get_batch_payment_term_date(self):
        self.ensure_one()
        return self.batch_id.end_date if self.batch_id else (self.invoice_date or self.date or fields.Date.context_today(self))

    @api.depends('invoice_payment_term_id', 'invoice_date', 'batch_id', 'batch_id.end_date', 'currency_id', 'amount_total_in_currency_signed', 'invoice_date_due')
    def _compute_needed_terms(self):
        batched_moves = self.filtered(lambda move: move.batch_id)
        standard_moves = self - batched_moves
        if standard_moves:
            super(AccountMove, standard_moves)._compute_needed_terms()
        if not batched_moves:
            return

        AccountTax = self.env['account.tax']
        for invoice in batched_moves.with_context(bin_size=False):
            is_draft = invoice.id != invoice._origin.id
            invoice.needed_terms = {}
            invoice.needed_terms_dirty = True
            sign = 1 if invoice.is_inbound(include_receipts=True) else -1
            if invoice.is_invoice(True) and invoice.invoice_line_ids:
                if invoice.invoice_payment_term_id:
                    if is_draft:
                        tax_amount_currency = 0.0
                        tax_amount = tax_amount_currency
                        untaxed_amount_currency = 0.0
                        untaxed_amount = untaxed_amount_currency
                        sign = invoice.direction_sign
                        base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines(round_from_tax_lines=False)
                        AccountTax._add_accounting_data_in_base_lines_tax_details(
                            base_lines,
                            invoice.company_id,
                            include_caba_tags=invoice.always_tax_exigible,
                        )
                        tax_results = AccountTax._prepare_tax_lines(base_lines, invoice.company_id)
                        for _base_line, to_update in tax_results['base_lines_to_update']:
                            untaxed_amount_currency += sign * to_update['amount_currency']
                            untaxed_amount += sign * to_update['balance']
                        for tax_line_vals in tax_results['tax_lines_to_add']:
                            tax_amount_currency += sign * tax_line_vals['amount_currency']
                            tax_amount += sign * tax_line_vals['balance']
                    else:
                        tax_amount_currency = invoice.amount_tax * sign
                        tax_amount = invoice.amount_tax_signed
                        untaxed_amount_currency = invoice.amount_untaxed * sign
                        untaxed_amount = invoice.amount_untaxed_signed
                    payment_term = invoice.invoice_payment_term_id.with_context(
                        customer_batch_end_date=invoice.batch_id.end_date,
                    )
                    invoice_payment_terms = payment_term._compute_terms(
                        date_ref=invoice._get_batch_payment_term_date(),
                        currency=invoice.currency_id or invoice.journal_id.currency_id or invoice.company_currency_id,
                        tax_amount_currency=tax_amount_currency,
                        tax_amount=tax_amount,
                        untaxed_amount_currency=untaxed_amount_currency,
                        untaxed_amount=untaxed_amount,
                        company=invoice.company_id,
                        cash_rounding=invoice.invoice_cash_rounding_id,
                        sign=sign,
                    )
                    for term_line in invoice_payment_terms['line_ids']:
                        key = frozendict({
                            'move_id': invoice.id,
                            'date_maturity': fields.Date.to_date(term_line.get('date')),
                            'discount_date': invoice_payment_terms.get('discount_date'),
                        })
                        values = {
                            'balance': term_line['company_amount'],
                            'amount_currency': term_line['foreign_amount'],
                            'discount_date': invoice_payment_terms.get('discount_date'),
                            'discount_balance': invoice_payment_terms.get('discount_balance') or 0.0,
                            'discount_amount_currency': invoice_payment_terms.get('discount_amount_currency') or 0.0,
                        }
                        if key not in invoice.needed_terms:
                            invoice.needed_terms[key] = values
                        else:
                            invoice.needed_terms[key]['balance'] += values['balance']
                            invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
                else:
                    invoice.needed_terms[frozendict({
                        'move_id': invoice.id,
                        'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
                        'discount_date': False,
                        'discount_balance': 0.0,
                        'discount_amount_currency': 0.0,
                    })] = {
                        'balance': invoice.amount_total_signed,
                        'amount_currency': invoice.amount_total_in_currency_signed,
                    }
