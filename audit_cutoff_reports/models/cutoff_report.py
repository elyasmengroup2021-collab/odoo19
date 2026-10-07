from collections import defaultdict
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_is_zero


class AccountCutoffReport(models.AbstractModel):
    _name = 'account.cutoff.report'
    _description = 'Audit Cut-off Report'

    REPORTS = {
        'bills_to_receive': ('Bills To Receive', 'purchase.order.line'),
        'billed_not_received': ('Billed Not Received', 'purchase.order.line'),
        'invoices_to_issue': ('Invoices To Be Issued', 'sale.order.line'),
        'invoiced_not_delivered': ('Invoiced Not Delivered', 'sale.order.line'),
    }

    @api.model
    def get_report_data(self, report_type, as_of_date, company_id=False, last_365=True):
        if report_type not in self.REPORTS:
            raise UserError(_('Unknown cut-off report.'))
        if not self.env.user.has_group('account.group_account_user'):
            raise AccessError(_('You do not have access to accounting cut-off reports.'))

        as_of_date = fields.Date.to_date(as_of_date) if as_of_date else fields.Date.context_today(self)
        company = self.env['res.company'].browse(company_id or self.env.company.id).exists() or self.env.company
        ctx = dict(self.env.context, accrual_entry_date=fields.Date.to_string(as_of_date))
        date_from = as_of_date - relativedelta(days=365) if last_365 else False

        if report_type in ('bills_to_receive', 'billed_not_received'):
            return self._purchase_report(report_type, as_of_date, company, ctx, date_from)
        return self._sale_report(report_type, as_of_date, company, ctx, date_from)

    def _date_domain(self, date_from, as_of_date):
        domain = [('order_id.date_order', '<=', fields.Datetime.to_string(datetime.combine(as_of_date, time.max)))]
        if date_from:
            domain.append(('order_id.date_order', '>=', fields.Datetime.to_string(datetime.combine(date_from, time.min))))
        return domain

    def _invoice_value(self, line, as_of_date, purchase):
        move_types = ('in_invoice', 'in_refund') if purchase else ('out_invoice', 'out_refund')
        total = 0.0
        for inv_line in line.invoice_lines.filtered(lambda l: l.move_id.state == 'posted' and l.move_id.move_type in move_types):
            if not inv_line.move_id.invoice_date or inv_line.move_id.invoice_date > as_of_date:
                continue
            value = inv_line.price_subtotal
            if inv_line.move_id.currency_id != line.currency_id:
                value = inv_line.move_id.currency_id._convert(
                    value, line.currency_id, line.company_id,
                    inv_line.move_id.invoice_date or as_of_date, round=False,
                )
            total += -value if inv_line.move_id.move_type in ('in_refund', 'out_refund') else value
        return total

    def _invoiced_qty_at_date(self, line, as_of_date, purchase):
        """Return invoiced quantity using only posted invoices dated on/before cutoff.

        Odoo Community 19 has ``qty_invoiced`` but it is not a historical field;
        therefore the historical quantity is computed from invoice lines here.
        """
        move_types = ('in_invoice', 'in_refund') if purchase else ('out_invoice', 'out_refund')
        qty = 0.0
        for inv_line in line.invoice_lines.filtered(
            lambda l: l.move_id.state == 'posted'
            and l.move_id.move_type in move_types
            and l.move_id.invoice_date
            and l.move_id.invoice_date <= as_of_date
        ):
            value = inv_line.product_uom_id._compute_quantity(
                inv_line.quantity, line.product_uom_id, rounding_method='HALF-UP'
            )
            qty += -value if inv_line.move_id.move_type in ('in_refund', 'out_refund') else value
        return qty

    def _received_qty_at_date(self, line, as_of_date, purchase):
        """Return delivered/received quantity from done stock moves at cutoff."""
        if not getattr(line, 'move_ids', False):
            return 0.0
        qty = 0.0
        for move in line.move_ids.filtered(
            lambda m: m.state == 'done'
            and m.date
            and fields.Datetime.to_datetime(m.date).date() <= as_of_date
        ):
            move_qty = move.product_uom._compute_quantity(
                move.quantity, line.product_uom_id, rounding_method='HALF-UP'
            )
            if purchase:
                qty += -move_qty if move._is_purchase_return() else move_qty
            else:
                qty += -move_qty if move.origin_returned_move_id else move_qty
        return qty

    def _purchase_report(self, report_type, as_of_date, company, ctx, date_from):
        Line = self.env['purchase.order.line'].sudo().with_company(company).with_context(ctx)
        domain = [
            ('company_id', '=', company.id),
            ('order_id.state', 'in', ('purchase', 'done')),
            ('display_type', '=', False),
            ('is_downpayment', '=', False),
            ('product_id', '!=', False),
        ] + self._date_domain(date_from, as_of_date)
        lines = Line.search(domain)
        rows = []
        total_qty = total_amount = 0.0
        invoice_links = stock_links = 0

        for line in lines:
            received = self._received_qty_at_date(line, as_of_date, True)
            billed = self._invoiced_qty_at_date(line, as_of_date, True)
            diff = received - billed
            if report_type == 'bills_to_receive':
                if diff <= 0:
                    continue
                qty = diff
                unit_price = line._get_gross_price_unit()
                amount = qty * unit_price
            else:
                if diff >= 0:
                    continue
                qty = -diff
                invoiced_value = self._invoice_value(line, as_of_date, True)
                received_value = received * line._get_gross_price_unit()
                amount = max(0.0, invoiced_value - received_value)
                unit_price = amount / qty if qty and not float_is_zero(amount, precision_rounding=line.currency_id.rounding) else line._get_gross_price_unit()

            if float_is_zero(amount, precision_rounding=line.currency_id.rounding):
                continue
            invoice_links += len(line.invoice_lines)
            stock_links += len(getattr(line, 'move_ids', self.env['stock.move']))
            rows.append(self._row(line, qty, unit_price, amount, True, received=received, billed=billed))
            total_qty += qty
            total_amount += amount

        return self._result(report_type, as_of_date, company, rows, total_qty, total_amount, {
            'candidate_lines': len(lines), 'report_lines': len(rows),
            'invoice_links': invoice_links, 'stock_moves': stock_links,
            'integration': 'account + om_account_accountant + purchase + purchase_stock',
        })

    def _sale_report(self, report_type, as_of_date, company, ctx, date_from):
        Line = self.env['sale.order.line'].sudo().with_company(company).with_context(ctx)
        domain = [
            ('company_id', '=', company.id),
            ('order_id.state', 'in', ('sale', 'done')),
            ('display_type', '=', False),
            ('is_downpayment', '=', False),
            ('product_id', '!=', False),
        ] + self._date_domain(date_from, as_of_date)
        lines = Line.search(domain)
        rows = []
        total_qty = total_amount = 0.0
        invoice_links = stock_links = 0

        for line in lines:
            delivered = self._received_qty_at_date(line, as_of_date, False)
            invoiced = self._invoiced_qty_at_date(line, as_of_date, False)
            diff = delivered - invoiced
            if report_type == 'invoices_to_issue':
                if diff <= 0:
                    continue
                qty = diff
                amount = self._invoice_value(line, as_of_date, False)
                if amount <= 0:
                    amount = qty * line._get_gross_price_unit()
                unit_price = amount / qty if qty else line._get_gross_price_unit()
            else:
                if diff >= 0:
                    continue
                qty = -diff
                posted = line.invoice_lines.filtered(lambda l: l.move_id.state == 'posted' and l.move_id.move_type in ('out_invoice', 'out_refund') and l.move_id.invoice_date and l.move_id.invoice_date <= as_of_date)
                remaining = qty
                invoiced_value = 0.0
                invoiced_qty = 0.0
                for inv_line in posted.sorted(key=lambda l: l.move_id.invoice_date or fields.Date.today(), reverse=True):
                    q = inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom_id, rounding_method='HALF-UP')
                    take = min(max(q, 0.0), remaining)
                    if take <= 0:
                        continue
                    invoiced_value += inv_line.price_subtotal * (take / q) if q else 0.0
                    invoiced_qty += take
                    remaining -= take
                    if remaining <= 0:
                        break
                unit_price = invoiced_value / invoiced_qty if invoiced_qty else line._get_gross_price_unit()
                amount = invoiced_value

            if float_is_zero(amount, precision_rounding=line.currency_id.rounding):
                continue
            invoice_links += len(line.invoice_lines)
            stock_links += len(getattr(line, 'move_ids', self.env['stock.move']))
            rows.append(self._row(line, qty, unit_price, amount, False, delivered=delivered, invoiced=invoiced))
            total_qty += qty
            total_amount += amount

        return self._result(report_type, as_of_date, company, rows, total_qty, total_amount, {
            'candidate_lines': len(lines), 'report_lines': len(rows),
            'invoice_links': invoice_links, 'stock_moves': stock_links,
            'integration': 'account + om_account_accountant + sale + sale_stock',
        })

    def _row(self, line, qty, unit_price, amount, purchase, **metrics):
        partner = line.partner_id if purchase else line.order_partner_id
        return {
            'id': line.id, 'order_id': line.order_id.id, 'order_name': line.order_id.name,
            'partner_id': partner.id, 'partner_name': partner.display_name,
            'product_id': line.product_id.id, 'product_name': line.product_id.display_name,
            'description': line.name or '',
            'salesperson': line.order_id.user_id.display_name if not purchase and line.order_id.user_id else '',
            'quantity': qty, 'uom': line.product_uom_id.display_name,
            'unit_price': unit_price, 'amount': amount,
            'currency': line.currency_id.symbol or line.currency_id.name,
            'currency_position': line.currency_id.position, 'currency_id': line.currency_id.id,
            'received': metrics.get('received', 0.0), 'billed': metrics.get('billed', 0.0),
            'delivered': metrics.get('delivered', 0.0), 'invoiced': metrics.get('invoiced', 0.0),
        }

    def _result(self, report_type, as_of_date, company, rows, total_qty, total_amount, diagnostics):
        rows.sort(key=lambda r: (r['partner_name'] or '', r['order_name'] or '', r['id']))
        partners = [{'id': r['partner_id'], 'name': r['partner_name']} for r in rows]
        products = [{'id': r['product_id'], 'name': r['product_name']} for r in rows]
        partners = list({p['id']: p for p in partners}.values())
        products = list({p['id']: p for p in products}.values())
        return {
            'title': self.REPORTS[report_type][0], 'as_of_date': fields.Date.to_string(as_of_date),
            'company_id': company.id, 'company_name': company.display_name,
            'rows': rows, 'total_qty': total_qty, 'total_amount': total_amount, 'count': len(rows),
            'partners': sorted(partners, key=lambda x: x['name']),
            'products': sorted(products, key=lambda x: x['name']), 'diagnostics': diagnostics,
        }

    @api.model
    def prepare_report_action(self, report_type, as_of_date=False, company_id=False, last365=True):
        if report_type not in self.REPORTS:
            raise UserError(_("Unknown cut-off report."))
        if not self.env.user.has_group("account.group_account_user"):
            raise AccessError(_("You do not have access to accounting cut-off reports."))
        as_of_date = fields.Date.to_date(as_of_date) if as_of_date else fields.Date.context_today(self)
        company = self.env["res.company"].browse(company_id or self.env.company.id).exists() or self.env.company
        # Build the snapshot without the UI default filter. The native SearchModel will apply
        # the "For the Last 365 Days" filter to the snapshot using a stored boolean.
        data = self.get_report_data(report_type, fields.Date.to_string(as_of_date), company.id, False)
        import uuid
        self.env["account.cutoff.report.line"].cleanup_old_sessions()
        session_key = uuid.uuid4().hex
        self.env["account.cutoff.report.line"].create_snapshot(
            session_key, report_type, as_of_date, company.id, data.get("rows", [])
        )
        view = self.env.ref("audit_cutoff_reports.view_cutoff_report_line_list")
        search_view = self.env.ref("audit_cutoff_reports.view_cutoff_report_line_search")
        return {
            "name": self.REPORTS[report_type][0],
            "type": "ir.actions.act_window",
            "res_model": "account.cutoff.report.line",
            "view_mode": "list",
            "views": [(view.id, "list")],
            "search_view_id": search_view.id,
            "domain": [("session_key", "=", session_key), ("user_id", "=", self.env.user.id)],
            "context": {
                "cutoff_session": session_key,
                "cutoff_report_type": report_type,
                "cutoff_as_of_date": fields.Date.to_string(as_of_date),
                "cutoff_company_id": company.id,
                "cutoff_last365": bool(last365),
                "cutoff_is_sale": report_type in ("invoices_to_issue", "invoiced_not_delivered"),
                "search_default_last_365": 1 if last365 else 0,
                "search_default_group_partner": 1,
            },
        }

    @api.model
    def action_create_accrual_wizard(self, report_type, line_ids, as_of_date, company_id=False):
        if report_type not in self.REPORTS or not line_ids:
            raise UserError(_('Select at least one line.'))
        model = self.REPORTS[report_type][1]
        company = self.env['res.company'].browse(company_id or self.env.company.id).exists() or self.env.company
        return {
            'name': _('Create Accrual Entries'), 'type': 'ir.actions.act_window',
            'res_model': 'account.accrued.orders.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {
                'active_model': model, 'active_ids': line_ids, 'active_id': line_ids[0],
                'default_company_id': company.id, 'accrual_entry_date': fields.Date.to_string(fields.Date.to_date(as_of_date)),
            },
        }
