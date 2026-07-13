import io
from itertools import groupby

import xlsxwriter

from odoo import models, fields, api, _


class ReportVendorAccountStatementPartnerLedger(models.AbstractModel):
    _name = "report.vendor_account_statement.report_vendor_partner_ledger"

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env.ref(
            "vendor_account_statement.action_report_vendor_partner_ledger")
        wizard = self.env['vendor.statement.wizard'].browse(docids)
        move_lines = wizard.prepare_data()
        result = {
            "doc_ids": docids,
            "doc_model": report.model,
            "date_start": wizard.date_start,
            "date_end": wizard.date_end,
            "partner_name": wizard.partner_id.name,
            "partner_language": wizard.partner_id.lang or 'en_US',
            "item_lines": move_lines['item_lines'],
            "item_lines_bills": move_lines['item_lines_bills'],
            "item_lines_refunds": move_lines['item_lines_refunds'],
            "item_lines_net": move_lines['item_lines_net'],
            "total_credit_refund": move_lines['total_credit_refund'],
            "current_balance": move_lines['current_balance'],
            "currency": move_lines['currency'],
            "amount_currency": move_lines['amount_currency'],
            "user_id": wizard.user_id.name,
        }
        company = self.env.user.company_id
        if 'header_img' in company._fields:
            result['header_img_data'] = company.header_img
        if 'footer_img' in company._fields:
            result['footer_img_data'] = company.footer_img
        return result


class VendorStatementWizard(models.TransientModel):
    _name = 'vendor.statement.wizard'
    _description = 'Vendor Account Statement Wizard'

    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    type = fields.Selection(
        string='Output Type',
        selection=[('view', 'View'),
                   ('pdf', 'PDF'),
                   ('xlsx', 'Excel')],
        required=True, default="pdf")

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain="[('supplier_rank','>', 0)]",
        required=True
    )
    product_ids = fields.Many2many('product.product', string='Products')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    # ─────────────────────────────────────────────
    #  XLSX Download
    # ─────────────────────────────────────────────
    def action_download_vendor_account_statement(self):
        return {
            'type': "ir.actions.act_url",
            'target': "self",
            'tag': 'reload',
            'url': '/web/content/download/vendor_statement_report/{id}/{date_start}/{date_end}'.format(
                id=self.partner_id.id,
                date_start=str(self.date_start),
                date_end=str(self.date_end))
        }

    def get_document_vendor_statement_report(self, response, id, date_start, date_end):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False})

        title_style = workbook.add_format({
            'font_name': 'Times', 'font_size': 16, 'bold': True, 'align': 'center'
        })
        header_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#1a4f72', 'font_size': 14,
            'color': 'white', 'bold': True,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'
        })
        text_style = workbook.add_format({
            'font_name': 'Times', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left'
        })
        bill_text_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#d4e6f1', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left'
        })
        bill_number_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#d4e6f1', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'
        })
        text_style_1 = workbook.add_format({
            'font_name': 'Times', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'
        })
        number_style = workbook.add_format({
            'font_name': 'Times', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'
        })
        refund_number_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#fde8d8', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'
        })
        refund_text_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#fde8d8', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left'
        })

        sheet = workbook.add_worksheet(name='كشف حساب مورد-{}'.format(id.name))
        sheet.set_default_row(25)
        sheet.set_column(0, 0, 12)
        sheet.set_column(1, 1, 30)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 20)
        sheet.set_column(4, 10, 15)

        sheet.merge_range('A1:K1', 'كشف حساب مورد : {}'.format(id.name), title_style)

        # Headers
        sheet.write(2, 0, 'التاريخ', header_style)
        sheet.write(2, 1, 'اسم المورد', header_style)
        sheet.write(2, 2, 'البيان', header_style)
        sheet.write(2, 3, 'اسم الصنف', header_style)
        sheet.write(2, 4, 'الكمية', header_style)
        sheet.write(2, 5, 'وحدة القياس', header_style)
        sheet.write(2, 6, 'السعر', header_style)
        sheet.write(2, 7, 'الخصم', header_style)
        sheet.write(2, 8, 'المبلغ', header_style)
        sheet.write(2, 9, 'المسدد', header_style)
        sheet.write(2, 10, 'الرصيد', header_style)

        row = 3
        aml_obj = self.env['account.move.line']
        payable_account_id = id.property_account_payable_id

        # Opening balance
        start_balance_aml_ids = aml_obj.search([
            ('account_id', '=', payable_account_id.id),
            ('partner_id', '=', id.id),
            ('move_id.state', '=', 'posted'),
            ('date', '<', date_start),
        ])
        start_balance = sum([l.balance for l in start_balance_aml_ids])

        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1), 'رصيد أول المدة', text_style_1)
        sheet.write(row, 4, 0, number_style)
        sheet.write(row, 5, 0, number_style)
        sheet.write(row, 6, 0, number_style)
        sheet.write(row, 7, 0, number_style)
        sheet.write(row, 8, 0, number_style)
        sheet.write(row, 9, 0, number_style)
        sheet.write(row, 10, start_balance, number_style)
        row += 1

        amls = aml_obj.search([
            ('account_id', '=', payable_account_id.id),
            ('partner_id', '=', id.id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_start),
            ('date', '<=', date_end),
        ], order='date ASC')

        if amls:
            # Vendor Bills (in_invoice)
            bill_amls = amls.filtered(
                lambda aml: aml.move_id.move_type == 'in_invoice' and not aml.payment_id
            )
            for bill_aml in bill_amls:
                for item in bill_aml.move_id:
                    for line in item.invoice_line_ids:
                        total_amount = line.price_subtotal
                        start_balance = start_balance - total_amount
                        sheet.write(row, 0, fields.Date.to_string(bill_aml.date) if bill_aml.date else " ", bill_text_style)
                        sheet.write(row, 1, bill_aml.partner_id.name, bill_text_style)
                        sheet.write(row, 2, 'مشتريات: {}'.format(bill_aml.name if bill_aml.name else bill_aml.ref or ''), bill_text_style)
                        sheet.write(row, 3, line.product_id.name if line.product_id else '', bill_text_style)
                        sheet.write(row, 4, line.quantity, bill_number_style)
                        sheet.write(row, 5, line.product_uom_id.name if line.product_uom_id else '', bill_number_style)
                        sheet.write(row, 6, line.price_unit, bill_number_style)
                        sheet.write(row, 7, str(line.discount) + '%' if line.discount else '0%', bill_number_style)
                        sheet.write(row, 8, total_amount, bill_number_style)
                        sheet.write(row, 9, 0, bill_number_style)
                        sheet.write(row, 10, round(start_balance, 2), bill_number_style)
                        row += 1

            # Payments
            payment_amls = amls.filtered(lambda aml: aml.payment_id)
            for payment_aml in payment_amls:
                paid = payment_aml.debit if payment_aml.payment_id else 0
                start_balance = start_balance + paid
                sheet.write(row, 0, fields.Date.to_string(payment_aml.date) if payment_aml.date else " ", text_style)
                sheet.write(row, 1, payment_aml.partner_id.name, text_style)
                sheet.write(row, 2, payment_aml.ref if payment_aml.ref else payment_aml.name or '', text_style)
                sheet.write(row, 3, payment_aml.product_id.name if payment_aml.product_id else " ", text_style)
                sheet.write(row, 4, 0, number_style)
                sheet.write(row, 5, '', number_style)
                sheet.write(row, 6, 0, number_style)
                sheet.write(row, 7, 0, number_style)
                sheet.write(row, 8, 0, number_style)
                sheet.write(row, 9, paid, number_style)
                sheet.write(row, 10, round(start_balance, 2), number_style)
                row += 1

            # Vendor Refunds (in_refund)
            refund_amls = amls.filtered(
                lambda aml: aml.move_id.move_type == 'in_refund' and not aml.payment_id
            )
            for refund_aml in refund_amls:
                for item in refund_aml.move_id:
                    for line in item.invoice_line_ids:
                        total_amount = line.price_subtotal
                        start_balance = start_balance + total_amount
                        sheet.write(row, 0, fields.Date.to_string(refund_aml.date) if refund_aml.date else " ", refund_text_style)
                        sheet.write(row, 1, refund_aml.partner_id.name, refund_text_style)
                        sheet.write(row, 2, 'مرتجعات مشتريات: {}'.format(item.name if item.name else item.ref or ''), refund_text_style)
                        sheet.write(row, 3, line.product_id.name if line.product_id else '', refund_text_style)
                        sheet.write(row, 4, line.quantity, refund_number_style)
                        sheet.write(row, 5, line.product_uom_id.name if line.product_uom_id else '', refund_number_style)
                        sheet.write(row, 6, line.price_unit, refund_number_style)
                        sheet.write(row, 7, str(line.discount) + '%' if line.discount else '0%', refund_number_style)
                        sheet.write(row, 8, total_amount, refund_number_style)
                        sheet.write(row, 9, 0, refund_number_style)
                        sheet.write(row, 10, round(start_balance, 2), refund_number_style)
                        row += 1

        # Totals row
        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1), _('Total'), header_style)
        sheet.write(row, 4, 0, header_style)
        sheet.write(row, 5, 0, header_style)
        sheet.write(row, 6, 0, header_style)
        sheet.write(row, 7, 0, header_style)
        sheet.write_formula(row, 8, '=SUM(I5:I' + str(row) + ')', header_style)
        sheet.write_formula(row, 9, '=SUM(J5:J' + str(row) + ')', header_style)
        sheet.write_formula(row, 10, '=K' + str(row), header_style)

        workbook.close()
        output.seek(0)
        generated_file = response.stream.write(output.read())
        output.close()
        return generated_file

    # ─────────────────────────────────────────────
    #  Opening Balance
    # ─────────────────────────────────────────────
    def get_opening_balance(self, partner):
        product_ids_filter = self.product_ids
        move_line_obj = self.env['account.move.line']
        domain = [
            ('partner_id', '=', partner.id),
            ('date', '<', self.date_start),
            ('move_id.state', '=', 'posted'),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        move_lines = move_line_obj.search(domain).sorted('date')
        opening_balance = 0
        for move_line in move_lines:
            if not product_ids_filter:
                opening_balance += move_line.debit - move_line.credit
            else:
                if move_line.move_id.move_type in ["in_invoice", "in_refund"]:
                    for invoice_line in move_line.move_id.invoice_line_ids:
                        product = invoice_line.product_id
                        if product_ids_filter and product not in product_ids_filter:
                            continue
                        if move_line.move_id.move_type == "in_invoice":
                            credit = invoice_line.price_subtotal
                            debit = 0.0
                        else:
                            credit = 0.0
                            debit = invoice_line.price_subtotal
                        opening_balance += debit - credit
                else:
                    debit = move_line.debit
                    credit = move_line.credit
                    if move_line.product_id:
                        if move_line.product_id not in product_ids_filter:
                            continue
                        opening_balance += debit - credit
                    else:
                        product_payment_ids = move_line.move_id.payment_id.product_payment_ids.filtered(
                            lambda p: p.product_id in product_ids_filter
                        ) if move_line.move_id.payment_id else []
                        if not product_payment_ids:
                            continue
                        debit = sum(product_payment_ids.mapped('amount_company_currency'))
                        opening_balance += debit - credit
        return opening_balance

    # ─────────────────────────────────────────────
    #  Format AML Name for Vendors
    # ─────────────────────────────────────────────
    @api.model
    def _format_aml_name(self, move_line):
        lang = self.partner_id.lang
        if move_line.move_id.move_type == "in_invoice":
            name = ('المشتريات : %s' if lang == 'ar_001' else 'Purchase: %s') % (
                move_line.name if move_line.name else move_line.ref or '')
        elif move_line.move_id.move_type == "in_refund":
            name = ('مردودات مشتريات : %s' if lang == 'ar_001' else 'Purchase Refunds: %s') % (
                move_line.name if move_line.name else move_line.ref or '')
        else:
            name = move_line.ref if move_line.ref else move_line.name or ''
        if not name:
            name = move_line.move_id.ref if move_line.move_id.ref else move_line.move_id.name or ''
        return name

    # ─────────────────────────────────────────────
    #  Prepare Data for PDF/View
    # ─────────────────────────────────────────────
    def prepare_data(self):
        move_line_obj = self.env['account.move.line']
        partner = self.partner_id
        product_ids_filter = self.product_ids
        items = {}
        item_lines = []
        domain = [
            ('partner_id', '=', partner.id),
            ('date', '>=', self.date_start),
            ('date', '<=', self.date_end),
            ('move_id.state', '=', 'posted'),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        move_lines = move_line_obj.search(domain).sorted('date')

        total_debit = total_credit = 0.0
        opening_balance = self.get_opening_balance(partner)
        current_balance = opening_balance

        opening_debit = 0.0
        opening_credit = 0.0
        if opening_balance > 0:
            opening_debit = opening_balance
            total_debit = opening_balance
        elif opening_balance < 0:
            opening_credit = opening_balance * -1
            total_credit = opening_balance * -1

        lang = self.partner_id.lang
        opening_val = {
            "opening_balance": 'رصيـــــــد أول المـــــــدة' if lang == 'ar_001' else 'Opening Balance',
            "partner_name": partner.name,
            "balance": opening_balance,
            "opening_debit": opening_debit,
            "opening_credit": opening_credit,
        }
        item_lines.append(opening_val)

        item_lines_bills = {}
        item_lines_refunds = {}
        item_lines_net = {}
        total_credit_refund = 0.0
        currency = ''
        amount_currency = ''
        invoices = []

        for move_line in move_lines:
            debit = move_line.debit
            credit = move_line.credit
            currency = move_line.company_id.currency_id.name
            amount_currency = move_line.currency_id.name

            if move_line.move_id.move_type in ["in_invoice", "in_refund"]:
                if move_line.move_id.id not in invoices:
                    invoices.append(move_line.move_id.id)
                    for invoice_line in move_line.move_id.invoice_line_ids:
                        product = invoice_line.product_id
                        if product_ids_filter and product not in product_ids_filter:
                            continue

                        qun = product and invoice_line.quantity or ''
                        uom = product and invoice_line.product_id.uom_name or ''
                        price = product and invoice_line.price_unit or ''
                        discount = product and str(invoice_line.discount) + '%' or '0%'
                        price_subtotal = product and invoice_line.price_subtotal or '0'

                        if price_subtotal == '0':
                            continue

                        price_subtotal_converted = invoice_line.currency_id._convert(
                            from_amount=price_subtotal,
                            to_currency=invoice_line.company_id.currency_id,
                            company=invoice_line.company_id,
                            date=move_line.date
                        )

                        if move_line.move_id.move_type == "in_invoice":
                            # Bill: vendor owes us → credit increases (we owe vendor)
                            line_credit = price_subtotal_converted
                            line_debit = 0.0
                        else:
                            # Refund: reduces what we owe
                            line_debit = price_subtotal_converted
                            line_credit = 0.0

                        balance = line_debit - line_credit
                        current_balance += balance

                        val = {
                            "date": move_line.date,
                            "ref": self._format_aml_name(move_line),
                            "product": product and product.name or '',
                            "qun": qun or '',
                            "uom": uom or '',
                            "price": price,
                            "discount": discount,
                            "total_price": price_subtotal,
                            "debit": round(line_debit, 2),
                            "credit": round(line_credit, 2),
                            "balance": current_balance,
                            "amount_currency": move_line.currency_id.name,
                        }
                        item_lines.append(val)
                        total_debit += line_debit
                        total_credit += line_credit

                        # Tax lines
                        total_tax = 0.0
                        tax_debit_total = 0.0
                        tax_credit_total = 0.0
                        if invoice_line.tax_ids:
                            for tax_line in invoice_line.tax_ids:
                                tax_name = tax_line.name
                                tax_amount_currency = (tax_line.amount / 100) * price_subtotal
                                tax_amount = invoice_line.currency_id._convert(
                                    from_amount=tax_amount_currency,
                                    to_currency=invoice_line.company_id.currency_id,
                                    company=invoice_line.company_id,
                                    date=move_line.date
                                )
                                total_tax += tax_amount_currency
                                if move_line.move_id.move_type == "in_invoice":
                                    if tax_amount >= 0:
                                        # ضريبة إضافية → تزيد المديونية → دائن
                                        tax_debit = 0.0
                                        tax_credit = tax_amount
                                        tax_credit_total += tax_credit
                                    else:
                                        # ضريبة خصم (Withholding) → تقلل المديونية → مدين
                                        tax_debit = abs(tax_amount)
                                        tax_credit = 0.0
                                        tax_debit_total += tax_debit
                                else:
                                    # in_refund: العكس
                                    if tax_amount >= 0:
                                        tax_debit = tax_amount
                                        tax_credit = 0.0
                                        tax_debit_total += tax_debit
                                    else:
                                        tax_debit = 0.0
                                        tax_credit = abs(tax_amount)
                                        tax_credit_total += tax_credit

                                t_balance = tax_debit - tax_credit
                                current_balance += t_balance
                                tax_val = {
                                    "date": move_line.date,
                                    "ref": self._format_aml_name(move_line),
                                    "product": tax_name or '',
                                    "qun": 0,
                                    "uom": '',
                                    "price": 0,
                                    "discount": 0,
                                    "total_price": abs(tax_amount_currency),
                                    "debit": round(tax_debit, 2),
                                    "credit": round(tax_credit, 2),
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name,
                                }
                                item_lines.append(tax_val)
                                total_debit += tax_debit
                                total_credit += tax_credit

                        if move_line.move_id.move_type == "in_invoice":
                            # net_credit = ما يستحقه المورد فعلاً (مشتريات - خصم ضريبي)
                            net_credit = round(line_credit + tax_credit_total - tax_debit_total, 2)

                            if product.id in item_lines_bills:
                                item_lines_bills[product.id]["qun"] += qun
                                item_lines_bills[product.id]["total_price"] += (price_subtotal + total_tax)
                                item_lines_bills[product.id]["credit"] += (line_credit + tax_credit_total)
                            else:
                                item_lines_bills[product.id] = {
                                    "product": product.name,
                                    "ref": 'المشتريات' if lang == 'ar_001' else 'Purchases',
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    "credit": round(line_credit + tax_credit_total, 2),
                                    "amount_currency": move_line.currency_id.name,
                                }

                            if product.id in item_lines_net:
                                item_lines_net[product.id]["qun"] += qun
                                item_lines_net[product.id]["total_price"] += (price_subtotal + total_tax)
                                item_lines_net[product.id]["debit"] += 0.0
                                item_lines_net[product.id]["credit"] += net_credit
                            else:
                                item_lines_net[product.id] = {
                                    "product": product.name,
                                    "ref": 'صافي المشتريات' if lang == 'ar_001' else 'Net Purchases',
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    "debit": 0.0,
                                    "credit": net_credit,
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name,
                                }
                        else:
                            # in_refund
                            total_credit_refund += round(line_debit, 2)
                            if product.id in item_lines_refunds:
                                item_lines_refunds[product.id]["qun"] += qun
                                item_lines_refunds[product.id]["total_price"] += (price_subtotal + total_tax)
                                item_lines_refunds[product.id]["debit"] += (line_debit + tax_debit_total)
                            else:
                                item_lines_refunds[product.id] = {
                                    "product": product.name,
                                    "ref": 'مرتجعات مشتريات' if lang == 'ar_001' else 'Purchase Returns',
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    "debit": round(line_debit + tax_debit_total, 2),
                                    "credit": 0.0,
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name,
                                }

                            if product.id in item_lines_net:
                                item_lines_net[product.id]["qun"] -= qun
                                item_lines_net[product.id]["total_price"] -= (price_subtotal + total_tax)
                                item_lines_net[product.id]["debit"] -= (line_debit + tax_debit_total)
                                item_lines_net[product.id]["credit"] -= (line_credit + tax_credit_total)
                            else:
                                item_lines_net[product.id] = {
                                    "product": product.name,
                                    "ref": 'صافي المشتريات' if lang == 'ar_001' else 'Net Purchases',
                                    "qun": -qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": -(price_subtotal + total_tax),
                                    "debit": -round(line_debit + tax_debit_total, 2),
                                    "credit": -round(line_credit + tax_credit_total, 2),
                                    "balance": -current_balance,
                                    "amount_currency": move_line.currency_id.name,
                                }
            else:
                # Payments and other entries
                if not product_ids_filter:
                    balance_currency = move_line.amount_currency
                    balance = debit - credit
                    current_balance += balance
                    val = {
                        "date": move_line.date,
                        "ref": self._format_aml_name(move_line),
                        "product": '',
                        "qun": 0,
                        "uom": '',
                        "price": 0,
                        "discount": 0,
                        "total_price": balance_currency,
                        "debit": round(debit, 2),
                        "credit": round(credit, 2),
                        "balance": current_balance,
                        "amount_currency": move_line.currency_id.name,
                    }
                    item_lines.append(val)
                    total_debit += debit
                    total_credit += credit
                else:
                    if move_line.product_id:
                        if move_line.product_id not in product_ids_filter:
                            continue
                        balance_currency = move_line.amount_currency
                        balance = debit - credit
                        current_balance += balance
                    else:
                        product_payment_ids = move_line.move_id.payment_id.product_payment_ids.filtered(
                            lambda p: p.product_id in product_ids_filter
                        ) if move_line.move_id.payment_id else []
                        if not product_payment_ids:
                            continue
                        balance_currency = sum(product_payment_ids.mapped('amount'))
                        debit = sum(product_payment_ids.mapped('amount_company_currency'))
                        balance = debit - credit
                        current_balance += balance

                    val = {
                        "date": move_line.date,
                        "ref": self._format_aml_name(move_line),
                        "product": '',
                        "qun": 0,
                        "uom": '',
                        "price": 0,
                        "discount": 0,
                        "total_price": balance_currency,
                        "debit": round(debit, 2),
                        "credit": round(credit, 2),
                        "balance": current_balance,
                        "amount_currency": move_line.currency_id.name,
                    }
                    item_lines.append(val)
                    total_debit += debit
                    total_credit += credit

        total_val = {
            "total_val": "total_val",
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "total_balance": round(total_debit - total_credit, 2),
        }
        item_lines.append(total_val)

        items.update({
            "item_lines": item_lines,
            "item_lines_bills": list(item_lines_bills.values()),
            "item_lines_refunds": list(item_lines_refunds.values()),
            "item_lines_net": list(item_lines_net.values()),
            "total_credit_refund": total_credit_refund,
            "current_balance": current_balance,
            "currency": currency,
            "amount_currency": amount_currency,
        })
        return items

    # ─────────────────────────────────────────────
    #  Actions
    # ─────────────────────────────────────────────
    def action_print_pdf(self):
        return self.env.ref(
            'vendor_account_statement.action_report_vendor_partner_ledger'
        ).with_context(
            lang=self.partner_id.lang or 'en_US'
        ).report_action(self)

    def action_view_report(self):
        """Open report as HTML inside Odoo - store wizard id in context for controller."""
        return {
            'type': 'ir.actions.act_url',
            'url': '/vendor_statement/view/{wizard_id}'.format(wizard_id=self.id),
            'target': 'new',
        }

    def action_download_xlsx(self):
        """Generate Excel in-memory and return as downloadable binary attachment."""
        import base64
        output = self._build_xlsx()
        filename = 'Vendor_Statement_{partner}_{date}.xlsx'.format(
            partner=self.partner_id.name.replace(' ', '_'),
            date=str(self.date_start),
        )
        # Save as ir.attachment then redirect to download URL
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{att_id}?download=true'.format(att_id=attachment.id),
            'target': 'self',
        }

    def _build_xlsx(self):
        """Build Excel using prepare_data() - identical content to PDF."""
        import io
        import xlsxwriter

        partner   = self.partner_id
        date_start = self.date_start
        date_end   = self.date_end

        # Reuse same data pipeline as PDF
        move_lines         = self.prepare_data()
        item_lines         = move_lines['item_lines']
        item_lines_bills   = move_lines['item_lines_bills']
        item_lines_refunds = move_lines['item_lines_refunds']
        item_lines_net     = move_lines['item_lines_net']
        currency           = move_lines['currency']

        output   = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False})

        # ── Formats ──────────────────────────────────────────────
        title_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 16, 'bold': True,
            'align': 'center', 'valign': 'vcenter',
        })
        period_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 11, 'bold': True,
            'align': 'center', 'fg_color': '#d0e4f7',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        header_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 12, 'bold': True,
            'color': 'white', 'fg_color': '#1a4f72',
            'align': 'center', 'valign': 'vcenter',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1, 'text_wrap': True,
        })
        opening_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 11, 'bold': True,
            'fg_color': '#eaf4fb', 'align': 'center',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        bill_txt_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#d4e6f1',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        bill_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#d4e6f1',
            'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        pay_txt_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#e9f7ef',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        pay_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#e9f7ef',
            'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        refund_txt_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#fde8d8',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        refund_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'fg_color': '#fde8d8',
            'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        total_lbl_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 12, 'bold': True,
            'color': 'white', 'fg_color': '#1a4f72',
            'align': 'center', 'valign': 'vcenter',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        total_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 12, 'bold': True,
            'color': 'white', 'fg_color': '#1a4f72',
            'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        opening_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 11, 'bold': True,
            'fg_color': '#eaf4fb', 'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        summary_lbl_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'bold': True,
            'fg_color': '#d5e8d4', 'align': 'center',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })
        summary_num_fmt = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'bold': True,
            'fg_color': '#d5e8d4', 'align': 'center', 'num_format': '#,##0.00',
            'left': 1, 'right': 1, 'top': 1, 'bottom': 1,
        })

        # ── Sheet ────────────────────────────────────────────────
        sheet = workbook.add_worksheet('كشف حساب مورد')
        sheet.right_to_left()
        sheet.set_row(0, 28)
        sheet.set_row(1, 20)
        sheet.set_row(2, 30)
        sheet.set_default_row(20)
        sheet.set_column(0, 0, 12)
        sheet.set_column(1, 1, 32)
        sheet.set_column(2, 2, 28)
        sheet.set_column(3, 3, 22)
        sheet.set_column(4, 4, 10)
        sheet.set_column(5, 5, 10)
        sheet.set_column(6, 6, 12)
        sheet.set_column(7, 7, 8)
        sheet.set_column(8, 8, 14)
        sheet.set_column(9, 9, 14)
        sheet.set_column(10, 10, 14)

        sheet.merge_range('A1:K1', 'كشف حساب مورد : {}'.format(partner.name), title_fmt)
        sheet.merge_range('A2:K2',
            'من : {}   إلى : {}'.format(str(date_start), str(date_end)), period_fmt)

        headers = ['التاريخ', 'البيان', 'اسم الصنف', 'الكمية',
                   'وحدة القياس', 'السعر', 'الخصم', 'المبلغ',
                   'مدين', 'دائن', 'الرصيد']
        for col, h in enumerate(headers):
            sheet.write(2, col, h, header_fmt)

        row = 3

        # ── Write rows from prepare_data() ───────────────────────
        for line in item_lines:
            # Opening balance row
            if line.get('opening_balance'):
                sheet.merge_range(row, 0, row, 7, line['opening_balance'], opening_fmt)
                od = round(line.get('opening_debit',  0), 2)
                oc = round(line.get('opening_credit', 0), 2)
                sheet.write(row, 8,  od if od else '', opening_num_fmt)
                sheet.write(row, 9,  oc if oc else '', opening_num_fmt)
                sheet.write(row, 10, round(line.get('balance', 0), 2), opening_num_fmt)
                row += 1
                continue

            # Totals row
            if line.get('total_val'):
                sheet.merge_range(row, 0, row, 7, 'الإجمالي', total_lbl_fmt)
                sheet.write(row, 8,  round(line.get('total_debit',   0), 2), total_num_fmt)
                sheet.write(row, 9,  round(line.get('total_credit',  0), 2), total_num_fmt)
                sheet.write(row, 10, round(line.get('total_balance', 0), 2), total_num_fmt)
                row += 1
                continue

            # Detect row type by content
            ref = line.get('ref', '') or ''
            if 'مشتريات' in ref or 'Purchase' in ref:
                txt_fmt, num_fmt = bill_txt_fmt, bill_num_fmt
            elif 'مرتجع' in ref or 'Refund' in ref or 'Return' in ref:
                txt_fmt, num_fmt = refund_txt_fmt, refund_num_fmt
            else:
                txt_fmt, num_fmt = pay_txt_fmt, pay_num_fmt

            sheet.write(row, 0,  str(line.get('date', '') or ''),           txt_fmt)
            sheet.write(row, 1,  str(line.get('ref',  '') or ''),           txt_fmt)
            sheet.write(row, 2,  str(line.get('product', '') or ''),        txt_fmt)
            sheet.write(row, 3,  line.get('qun', '') or '',                txt_fmt)
            sheet.write(row, 4,  str(line.get('uom', '') or ''),           txt_fmt)
            sheet.write(row, 5,  line.get('price', 0) or 0,                    num_fmt)
            sheet.write(row, 6,  str(line.get('discount', '') or ''),      txt_fmt)
            sheet.write(row, 7,  line.get('total_price', 0) or 0,              num_fmt)
            # Debit: show only if > 0
            dbt = round(line.get('debit',  0) or 0, 2)
            crd = round(line.get('credit', 0) or 0, 2)
            sheet.write(row, 8,  dbt if dbt else '', num_fmt)
            sheet.write(row, 9,  crd if crd else '', num_fmt)
            sheet.write(row, 10, round(line.get('balance', 0) or 0, 2),        num_fmt)
            row += 1

        # ── Summary sections (Bills / Refunds / Net) ─────────────
        def write_summary(lines, label_color, num_color):
            nonlocal row
            if not lines:
                return
            for i, line in enumerate(lines):
                if i == 0:
                    sheet.write(row, 0, '', label_color)
                    sheet.write(row, 1, line.get('ref', ''), label_color)
                else:
                    sheet.write(row, 0, '', label_color)
                    sheet.write(row, 1, '', label_color)
                sheet.write(row, 2,  line.get('product', ''),     label_color)
                sheet.write(row, 3,  line.get('qun', 0),            num_color)
                sheet.write(row, 4,  line.get('uom', ''),         label_color)
                sheet.write(row, 5,  line.get('price', 0) or 0,     num_color)
                sheet.write(row, 6,  line.get('discount', ''),    label_color)
                sheet.write(row, 7,  line.get('total_price', 0),    num_color)
                sheet.write(row, 8,  round(line.get('debit',  0) or 0, 2), num_color)
                sheet.write(row, 9,  round(line.get('credit', 0) or 0, 2), num_color)
                sheet.write(row, 10, round(line.get('balance', 0) or 0, 2), num_color)
                row += 1

        write_summary(item_lines_bills,   summary_lbl_fmt, summary_num_fmt)
        write_summary(item_lines_refunds, refund_txt_fmt,  refund_num_fmt)
        write_summary(item_lines_net,     total_lbl_fmt,   total_num_fmt)

        workbook.close()
        output.seek(0)
        return output.read()

    def action_download(self):
        if self.type == 'xlsx':
            return self.action_download_xlsx()
        elif self.type == 'view':
            return self.action_view_report()
        else:
            return self.action_print_pdf()
