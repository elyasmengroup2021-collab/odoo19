import io

from odoo import models, fields, api, _


class Reportcustomer_account_statement_partner_ladger(models.AbstractModel):
    _name = "report.customer_account_statement.report_partner_ledger"

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env["ir.actions.report"]._get_report_from_name(
            "customer_account_statement.report_partner_ledger")
        options_data = data or {}
        has_report_payload = bool(options_data.get('item_lines') or options_data.get('item_lines_invoices')
                                  or options_data.get('item_lines_refunds') or options_data.get('item_lines_net'))
        if not has_report_payload:
            wizard_model = self.env['customer.statement.wizard']
            wizard = wizard_model.browse(docids[:1]).exists()
            if not wizard and self.env.context.get('active_id'):
                wizard = wizard_model.browse(self.env.context.get('active_id')).exists()
            if not wizard:
                wizard = wizard_model.search([('create_uid', '=', self.env.uid)], order='id desc', limit=1)
            if wizard:
                options_data = wizard._prepare_report_data()
        return {
            "doc_ids": docids,
            "doc_model": report.model,
            "partner_name": options_data.get("partner_name"),
            "partner_language": options_data.get("partner_language") or 'en_US',
            "user_id": options_data.get("user_id") or '',
            "item_lines": options_data.get("item_lines", []),
            "item_lines_invoices": options_data.get("item_lines_invoices", []),
            "item_lines_refunds": options_data.get("item_lines_refunds", []),
            "item_lines_net": options_data.get("item_lines_net", []),
            "total_credit_refund": options_data.get("total_credit_refund", 0),
            "current_balance": options_data.get("current_balance", 0),
            "currency": options_data.get("currency"),
            "amount_currency": options_data.get("amount_currency"),
        }


class CustomerStatementWizard(models.TransientModel):
    _name = 'customer.statement.wizard'

    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    type = fields.Selection(
        string='Type',
        selection=[('pdf', 'PDF'),
                   ('xlsx', 'XLSX')],
        required=False, default="pdf")

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="[('customer_rank', '>', 0)]",
        required=True,
    )
    product_ids = fields.Many2many('product.product', string='Products')

    def action_download_customer_account_statement(self):
        return {
            'type': "ir.actions.act_url",
            'target': "self",
            'tag': 'reload',
            'url': '/customer_account_statement/download/xlsx/{id}/{date_start}/{date_end}'.format(
                id=self.partner_id.id, date_start=str(self.date_start), date_end=str(self.date_end))
        }

    def get_document_customer_statement_report(self, response, id, date_start, date_end):
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False, })
        title_style = workbook.add_format({'font_name': 'Times', 'font_size': 16, 'bold': True, 'align': 'center'})
        header_style = workbook.add_format(
            {'font_name': 'Times', 'fg_color': '#071f75', 'font_size': 14, 'color': 'white', 'bold': True, 'left': 1,
             'bottom': 1,

             'right': 1, 'top': 1,
             'align': 'center'})
        text_style = workbook.add_format(
            {'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left'})
        invoice_text_style = workbook.add_format(
            {'font_name': 'Times', 'fg_color': '#dac711', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1,
             'align': 'left'})
        invoice_number_style = workbook.add_format(
            {'font_name': 'Times', 'fg_color': '#dac711', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1,
             'align': 'center'})

        text_style_1 = workbook.add_format(
            {'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1,
             'align': 'center'})
        number_style = workbook.add_format(
            {'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center'})

        refund_number_style = workbook.add_format(
            {'font_name': 'Times', 'fg_color': '#da5b11', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1,
             'align': 'center'})
        refund_text_style = workbook.add_format(
            {'font_name': 'Times', 'fg_color': '#da5b11', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1,
             'align': 'left'})
        sheet = workbook.add_worksheet(name='كشف حساب عميل-{}'.format(id.name))
        sheet.set_default_row(25)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 25)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 25)
        sheet.merge_range('A1:M1', 'كشف حســاب عميل : {}'.format(id.name),
                          title_style)
        sheet.write(2, 0, 'التاريخ', header_style)
        sheet.write(2, 1, 'اسم العميل', header_style)
        sheet.write(2, 2, 'البيان', header_style)
        sheet.write(2, 3, 'اسم الصنف', header_style)
        sheet.write(2, 4, 'ك. بالطن', header_style)
        sheet.write(2, 5, 'ك. بالشيكارة ', header_style)
        sheet.write(2, 6, 'س. الطن', header_style)
        sheet.write(2, 7, 'س. الشيكارة', header_style)
        sheet.write(2, 8, 'الخصم', header_style)
        sheet.write(2, 9, 'قيمة', header_style)
        sheet.write(2, 10, 'الاجمالى', header_style)
        sheet.write(2, 11, 'المسـدد', header_style)
        sheet.write(2, 12, 'الرصيد', header_style)
        row = 3
        number = 1
        aml_obj = self.env['account.move.line']
        start_balance_aml_ids = aml_obj.search(
            [
                ('account_id.account_type', '=', 'asset_receivable'),
                ('partner_id', '=', id.id),
                ('move_id.state', '=', 'posted'),
                ('date', '<', date_start),
            ]
        )
        start_balance = sum([l.balance for l in start_balance_aml_ids])
        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1),
                          'رصــيد أول المــدة',
                          text_style_1)
        sheet.write(row, 4, 0, number_style)
        sheet.write(row, 5, 0, number_style)
        sheet.write(row, 6, 0, number_style)
        sheet.write(row, 7, 0, number_style)
        sheet.write(row, 8, 0, number_style)
        sheet.write(row, 9, 0, number_style)
        sheet.write(row, 10, 0, number_style)
        sheet.write(row, 11, 0, number_style)
        sheet.write(row, 12, start_balance, number_style)
        row += 1
        number += 1
        total_t = []
        total_shikara = []
        total_sale_refund_amount = []
        amls = aml_obj.search(
            [
                ('account_id.account_type', '=', 'asset_receivable'),
                ('partner_id', '=', id.id),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', date_start),
                ('date', '<=', date_end)
            ], order='date ASC'
        )
        if amls:
            sale_amls = amls.filtered(lambda aml: aml.move_id.move_type == 'out_invoice' and not aml.payment_id)
            if sale_amls:
                for sale_aml in sale_amls:
                    for item in sale_aml.move_id:
                        for line in item.invoice_line_ids:
                            bag_weight = getattr(line.product_id, 'bag_weight', 0) or 5
                            no_bags = 1000 / bag_weight
                            n_o_tons = 0.0
                            t = 0.0
                            if line.product_uom_id.name == 'kg' or line.product_uom_id.name == 'كجم':
                                n_o_tons = line.quantity / 1000
                            if line.product_uom_id.name == 't' or line.product_uom_id.name == 'طن':
                                t = line.quantity
                            total_amount = (n_o_tons if n_o_tons else t) * (
                                line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit) - ((
                                                                                                          (
                                                                                                              n_o_tons if n_o_tons else t) * (
                                                                                                              line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit) *
                                                                                                          (
                                                                                                              line.discount)) / 100)
                            start_balance = start_balance + total_amount
                            sheet.write(row, 0, fields.Date.to_string(sale_aml.date) if sale_aml.date else " ",
                                        invoice_text_style)
                            sheet.write(row, 1, sale_aml.partner_id.name, invoice_text_style)
                            sheet.write(row, 2,
                                        "{}".format(
                                            _('Sales: %s') % (sale_aml.name if sale_aml.name else sale_aml.ref)
                                        ),
                                        invoice_text_style)
                            sheet.write(row, 3, line.product_id.name if line.product_id.name else False,
                                        invoice_text_style)
                            total_t.append(n_o_tons if n_o_tons > 0.0 else t)
                            sheet.write(row, 4, n_o_tons if n_o_tons > 0.0 else t, invoice_number_style)
                            total_shikara.append(n_o_tons * no_bags if n_o_tons > 0.0 else t * no_bags)
                            sheet.write(row, 5, n_o_tons * no_bags if n_o_tons > 0.0 else t * no_bags,
                                        invoice_number_style)
                            sheet.write(row, 6, line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit,
                                        invoice_number_style)
                            sheet.write(row, 7,
                                        (line.price_unit * 1000) / no_bags if n_o_tons > 0.0 else (
                                                line.price_unit / no_bags),
                                        invoice_number_style)
                            sheet.write(row, 8, line.discount if line.discount else 0,
                                        invoice_number_style)
                            total_sale_refund_amount.append(total_amount)
                            sheet.write(row, 9, total_amount,
                                        invoice_number_style)

                            sheet.write(row, 10, total_amount,
                                        invoice_number_style)

                            sheet.write(row, 11, 0, invoice_number_style)
                            sheet.write(row, 12, round(start_balance, 2),
                                        invoice_number_style)
                            row += 1
                            number += 1
            payment_amls = amls.filtered(lambda aml: aml.payment_id)
            if payment_amls:
                for payments_aml in payment_amls:
                    start_balance = start_balance - (payments_aml.credit if payments_aml.payment_id else 0)
                    sheet.write(row, 0, fields.Date.to_string(payments_aml.date) if payments_aml.date else " ",
                                text_style)
                    sheet.write(row, 1, payments_aml.partner_id.name, text_style)
                    sheet.write(row, 2, payments_aml.ref if payments_aml.ref else payments_aml.name, text_style)
                    sheet.write(row, 3, payments_aml.product_id.name if payments_aml.product_id.name else " ",
                                text_style)
                    sheet.write(row, 4, 0, number_style)
                    sheet.write(row, 5, 0, number_style)
                    sheet.write(row, 6, 0, number_style)
                    sheet.write(row, 7, 0, number_style)
                    sheet.write(row, 8, 0, number_style)
                    sheet.write(row, 9, 0, number_style)
                    sheet.write(row, 10, 0, number_style)
                    sheet.write(row, 11, payments_aml.credit if payments_aml.payment_id else 0, number_style)
                    sheet.write(row, 12, round(start_balance, 2), number_style)
                    row += 1
                    number += 1
            refunds_amls = amls.filtered(lambda aml: aml.move_id.move_type == 'out_refund' and not aml.payment_id)
            if refunds_amls:
                for refunds_aml in refunds_amls:
                    for item in refunds_aml.move_id:
                        for line in item.invoice_line_ids:
                            bag_weight = getattr(line.product_id, 'bag_weight', 0) or 5
                            no_bags = 1000 / bag_weight
                            n_o_tons = 0.0
                            t = 0.0
                            if line.product_uom_id.name == 'kg' or line.product_uom_id.name == 'كجم':
                                n_o_tons = line.quantity / 1000
                            if line.product_uom_id.name == 't' or line.product_uom_id.name == 'طن':
                                t = line.quantity
                            total_amount = (n_o_tons if n_o_tons else t) * (
                                line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit) - ((
                                                                                                          (
                                                                                                              n_o_tons if n_o_tons else t) * (
                                                                                                              line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit) *
                                                                                                          (
                                                                                                              line.discount)) / 100)
                            start_balance = start_balance - total_amount
                            sheet.write(row, 0, fields.Date.to_string(refunds_aml.date) if refunds_aml.date else " ",
                                        refund_text_style)
                            sheet.write(row, 1, refunds_aml.partner_id.name, refund_text_style)
                            sheet.write(row, 2, 'مرتجعـــات:{}'.format(
                                item.name if item.name else item.ref), refund_text_style)
                            sheet.write(row, 3, line.product_id.name if line.product_id.name else False,
                                        refund_text_style)
                            total_t.append(-1 * n_o_tons if n_o_tons > 0.0 else -1 * t)

                            sheet.write(row, 4, n_o_tons if n_o_tons > 0.0 else t, refund_number_style)
                            total_shikara.append((-1 * n_o_tons * no_bags) if n_o_tons > 0.0 else (-1 * t * no_bags))
                            sheet.write(row, 5, n_o_tons * no_bags if n_o_tons > 0.0 else t * no_bags,
                                        refund_number_style)
                            sheet.write(row, 6, line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit,
                                        refund_number_style)
                            sheet.write(row, 7,
                                        (line.price_unit * 1000) / no_bags if n_o_tons > 0.0 else (
                                                line.price_unit / no_bags),
                                        refund_number_style)
                            sheet.write(row, 8, line.discount if line.discount else 0,
                                        refund_number_style)
                            total_sale_refund_amount.append(-1 * total_amount)
                            sheet.write(row, 9, total_amount,
                                        refund_number_style)
                            sheet.write(row, 10, total_amount,
                                        refund_number_style)
                            sheet.write(row, 11, 0,
                                        refund_number_style)
                            sheet.write(row, 12, round(start_balance, 2),
                                        refund_number_style)
                            row += 1
                            number += 1

        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1),
                          _('Total'),
                          header_style)
        sheet.write(row, 4, sum(total_t), header_style)
        sheet.write(row, 5, sum(total_shikara), header_style)
        sheet.write(row, 6, 0, header_style)
        sheet.write(row, 7, 0, header_style)
        sheet.write(row, 8, 0, header_style)
        sheet.write(row, 9, sum(total_sale_refund_amount), header_style)
        sheet.write(row, 10, sum(total_sale_refund_amount), header_style)
        sheet.write_formula(row, 11, '=SUM(L5:L' + str(row) + ')', header_style)
        sheet.write_formula(row, 12, '=M' + str(row), header_style)
        workbook.close()
        output.seek(0)
        generated_file = response.stream.write(output.read())
        output.close()

        return generated_file

    def get_opening_balance(self, partner):
        product_ids_filter = self.product_ids
        move_line_opj = self.env['account.move.line']
        # receivable = self.env.ref('account.data_account_type_receivable').id
        # domain = [('partner_id', '=', partner.id), ('date', '<', self.date_start),
        #           ('move_id.state', '=', 'posted'), ('parent_state', '!=', 'cancel'),
        #           ('account_id.user_type_id', 'in', [receivable, ])]
        domain = [('partner_id', '=', partner.id), ('date', '<', self.date_start),
                  ('move_id.state', '=', 'posted'), ('parent_state', '!=', 'cancel'),
                  ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable'])]
        move_lines = move_line_opj.search(domain).sorted('date')
        opening_balance = 0
        for move_line in move_lines:
            if not product_ids_filter:
                opening_balance += move_line.debit - move_line.credit
            else:
                if move_line.move_id.move_type in ["out_invoice", "out_refund"]:
                    for invoice_line in move_line.move_id.invoice_line_ids:
                        product = invoice_line.product_id
                        if product_ids_filter and product not in product_ids_filter:
                            continue
                        if move_line.move_id.move_type in ["out_invoice"]:
                            debit = invoice_line.price_subtotal
                            credit = 0.0
                        else:
                            debit = 0.0
                            credit = invoice_line.price_subtotal
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

                        credit = sum(product_payment_ids.mapped('amount_company_currency'))
                        opening_balance += debit - credit

        return opening_balance

    @api.model
    def _format_aml_name(self, move_line):
        lang = self.partner_id.lang
        if move_line.move_id.move_type == "out_invoice":
            name = ('%s : المبيعات'if lang == 'ar_001' else 'Sales: %s') % (move_line.name if move_line.name else move_line.ref)
        elif move_line.move_id.move_type == "out_refund":
            name = ('مردودات مبيعات : %s'if lang == 'ar_001' else 'Sales Refunds: %s') % (move_line.name if move_line.name else move_line.ref)
        else:
            name = move_line.ref if move_line.ref else move_line.name
        if not name:
            name = move_line.move_id.ref if move_line.move_id.ref else move_line.move_id.name

        return name

    def prepare_data(self):
        move_line_opj = self.env['account.move.line']
        # receivable = self.env.ref('account.data_account_type_receivable').id
        partner = self.partner_id
        product_ids_filter = self.product_ids
        items = {}
        item_lines = []
        domain = [('partner_id', '=', partner.id), ('date', '>=', self.date_start), ('date', '<=', self.date_end),
                  ('move_id.state', '=', 'posted'), ('parent_state', '!=', 'cancel'),
                  ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable'])]
        move_lines = move_line_opj.search(domain).sorted('date')
        # item_lines_invoices = move_lines.filtered(lambda l: l.move_id.move_type == "out_invoice")
        # item_lines_refunds = move_lines.filtered(lambda l: l.move_id.move_type == "out_refund")
        total_debit = total_credit = total_balance = 0.0
        opening_balance = self.get_opening_balance(partner)
        print("opening_balance", opening_balance)
        current_balance = opening_balance
        opening_debit = 0.0
        opening_credit = 0.0
        if opening_balance > 0:
            opening_debit = opening_balance
            total_debit = opening_balance
        elif opening_balance < 0:
            opening_credit = opening_balance * -1
            total_credit = opening_balance * -1
        lang =  self.partner_id.lang
        print(lang)
        opening_val = {
            "opening_balance": 'رصيـــــــد أول المـــــــدة' if lang == 'ar_001' else 'Opening Balance',
            "partner_name": partner.name,
            "balance": opening_balance,
            "opening_debit": opening_debit,
            "opening_credit": opening_credit,
        }
        item_lines.append(opening_val)
        item_lines_invoices = {}
        item_lines_refunds = {}
        item_lines_net = {}
        total_credit_refund = 0.0
        currency = ''
        amount_currency = ''
        invoices = []

        for move_line in move_lines:

            debit = move_line.debit
            credit = move_line.credit
            currency = move_line.company_currency_id.name
            amount_currency = move_line.currency_id.name
            if move_line.move_id.move_type in ["out_invoice", "out_refund"]:
                if move_line.move_id.id not in invoices:
                    invoices.append(move_line.move_id.id)
                    for invoice_line in move_line.move_id.invoice_line_ids:
                        product = invoice_line.product_id

                        # ####### filter with product ###############
                        # # if wizard have product must filter with it
                        if product_ids_filter and product not in product_ids_filter:
                            continue

                        # bag_weight = invoice_line.product_id.bag_weight if invoice_line.product_id.bag_weight > 0 else 1
                        qun = product and invoice_line.quantity or ''
                        uom = product and invoice_line.product_id.uom_name or ''
                        price = product and invoice_line.price_unit * 1000 or ''
                        # discount = product and (invoice_line.price_unit * invoice_line.quantity) * (invoice_line.discount / 100) or ''
                        discount = product and str(invoice_line.discount) + '%' or '0%'
                        price_subtotal = product and invoice_line.price_subtotal or '0'
                        price_subtotal_converted = 0
                        if price_subtotal == '0':
                            continue
                        price_subtotal_converted = invoice_line.currency_id._convert(from_amount=price_subtotal,
                                                                                     to_currency=invoice_line.company_id.currency_id,
                                                                                     company=invoice_line.company_id,
                                                                                     date=move_line.date)

                        if move_line.move_id.move_type in ["out_invoice"]:
                            debit = price_subtotal_converted
                            credit = 0.0
                        else:
                            debit = 0.0
                            credit = price_subtotal_converted
                        balance = debit - credit
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
                            "debit": round(debit, 2),
                            "credit": round(credit, 2),
                            "balance": current_balance,
                            "amount_currency": move_line.currency_id.name
                        }
                        item_lines.append(val)
                        total_debit += debit
                        total_credit += credit

                        # Construct Taxes
                        total_tax = 0.0
                        tax_debit = 0.0
                        tax_credit = 0.0
                        tax_debit_total = 0.0
                        tax_credit_total = 0.0
                        if invoice_line.tax_ids:
                            for tax_line in invoice_line.tax_ids:
                                tax_name = tax_line.name
                                tax_amount_currency = (tax_line.amount / 100) * price_subtotal
                                tax_amount = invoice_line.currency_id._convert(from_amount=tax_amount_currency,
                                                                               to_currency=invoice_line.company_id.currency_id,
                                                                               company=invoice_line.company_id,
                                                                               date=move_line.date)
                                total_tax += tax_amount_currency
                                if move_line.move_id.move_type in ["out_invoice"]:
                                    if tax_amount > 0:
                                        tax_debit = tax_amount
                                        tax_debit_total += tax_debit
                                        tax_credit = 0.0
                                    else:
                                        tax_debit = 0.0
                                        tax_credit = tax_amount * -1
                                        tax_credit_total += tax_credit
                                else:
                                    if tax_amount > 0:
                                        tax_debit = 0.0
                                        tax_credit = tax_amount
                                        tax_credit_total += tax_amount
                                    else:
                                        tax_debit = tax_amount * -1
                                        tax_debit_total += tax_debit
                                        tax_credit = 0.0
                                balance = tax_debit - tax_credit
                                current_balance += balance
                                val = {
                                    "date": move_line.date,
                                    "ref": self._format_aml_name(move_line),
                                    "product": tax_name or '',
                                    "ton": 0,
                                    "bags": 0,
                                    "price": 0,
                                    "discount": 0,
                                    "total_price": tax_amount_currency,
                                    "debit": round(tax_debit, 2),
                                    "credit": round(tax_credit, 2),
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name
                                }
                                item_lines.append(val)
                                total_debit += tax_debit
                                total_credit += tax_credit

                        if move_line.move_id.move_type == "out_invoice":
                            if product.id in item_lines_invoices.keys():
                                # item_lines_invoices[product.id]["ton"] += ton
                                # item_lines_invoices[product.id]["bags"] += bags
                                # item_lines_invoices[product.id]["price"] = price
                                item_lines_invoices[product.id]["qun"] += qun
                                item_lines_invoices[product.id]["total_price"] += (price_subtotal + total_tax)
                                # item_lines_invoices[product.id]["debit"] += debit
                                item_lines_invoices[product.id]["credit"] += (credit + tax_credit_total)
                                # item_lines_invoices[product.id]["balance"] += current_balance
                            else:
                                lang=self.partner_id.lang
                                item_lines_invoices[product.id] = {
                                    "product": product.name,
                                    "ref": 'المبيعات' if lang == 'ar_001' else 'Sales',
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    # "debit": round(debit, 2),
                                    "credit": round(credit, 2),
                                    # "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name
                                }

                            if product.id in item_lines_net.keys():
                                item_lines_net[product.id]["qun"] += qun
                                # item_lines_net[product.id]["bags"] += bags
                                # item_lines_invoices[product.id]["price"] = price
                                item_lines_net[product.id]["total_price"] += (price_subtotal + total_tax)
                                item_lines_net[product.id]["debit"] += (debit + tax_debit_total)
                                item_lines_net[product.id]["credit"] += (credit + tax_credit_total)
                                item_lines_net[product.id]["balance"] += current_balance
                            else:
                                item_lines_net[product.id] = {
                                    "product": product.name,
                                    "ref": _('Net Sales'),
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    "debit": round(debit + tax_debit_total, 2),
                                    "credit": round(credit + tax_credit_total, 2),
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name
                                }
                        else:
                            total_credit_refund += round(credit, 2)
                            if product.id in item_lines_refunds.keys():
                                item_lines_refunds[product.id]["qun"] += qun
                                # item_lines_refunds[product.id]["bags"] += bags
                                # item_lines_refunds[product.id]["price"] = price
                                item_lines_refunds[product.id]["total_price"] += (price_subtotal + total_tax)
                                # item_lines_refunds[product.id]["debit"] += debit
                                item_lines_refunds[product.id]["credit"] += (credit + tax_credit_total)
                                item_lines_refunds[product.id]["balance"] += current_balance
                            else:
                                lang=self.partner_id.lang
                                item_lines_refunds[product.id] = {
                                    "product": product.name,
                                    "ref": 'مرتجعات' if lang == 'ar_001' else 'Returns',
                                    "qun": qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": price_subtotal + total_tax,
                                    "debit": 0.0,
                                    "credit": round(credit + tax_credit_total, 2),
                                    "balance": current_balance,
                                    "amount_currency": move_line.currency_id.name
                                }

                            if product.id in item_lines_net.keys():
                                item_lines_net[product.id]["qun"] -= qun
                                item_lines_net[product.id]["uom"] = uom
                                # item_lines_invoices[product.id]["price"] = price
                                item_lines_net[product.id]["total_price"] -= (price_subtotal + total_tax)
                                item_lines_net[product.id]["debit"] -= (debit + tax_debit_total)
                                item_lines_net[product.id]["credit"] -= (credit + tax_credit_total)
                                item_lines_net[product.id]["balance"] -= current_balance
                            else:
                                lang=self.partner_id.lang
                                item_lines_net[product.id] = {
                                    "product": product.name,
                                    "ref":  'صافي المبيعات' if lang == 'ar_001' else 'Net Sales',
                                    "qun": -qun,
                                    "uom": uom,
                                    "price": price,
                                    "discount": 0.0,
                                    "total_price": -(price_subtotal + total_tax),
                                    "debit": -round(debit + tax_debit_total, 2),
                                    "credit": -round(credit + tax_credit_total, 2),
                                    "balance": -current_balance,
                                    "amount_currency": move_line.currency_id.name,
                                }

            else:
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
                    # ####### filter with product ###############
                    if move_line.product_id:
                        if move_line.product_id not in product_ids_filter:
                            continue
                        balance_currency = move_line.amount_currency
                        balance = debit - credit
                        current_balance += balance
                    else:
                        # if has same product continue and get amount from it else discard
                        product_payment_ids = move_line.move_id.payment_id.product_payment_ids.filtered(
                            lambda p: p.product_id in product_ids_filter
                        ) if move_line.move_id.payment_id else []

                        if not product_payment_ids:
                            continue

                        balance_currency = sum(product_payment_ids.mapped('amount'))
                        credit = sum(product_payment_ids.mapped('amount_company_currency'))
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
                        "total_price": balance_currency * -1,
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

        # item_lines_invoices = list(item_lines_invoices.values())
        # item_lines_invoices.append({
        #     "total_debit": total_debit
        # })

        items.update(
            {
                "item_lines": item_lines,
                "item_lines_invoices": list(item_lines_invoices.values()),
                "item_lines_refunds": list(item_lines_refunds.values()),
                "item_lines_net": list(item_lines_net.values()),
                "total_credit_refund": total_credit_refund,
                "current_balance": current_balance,
                "currency": currency,
                "amount_currency": amount_currency,
            })
        return items

    def _prepare_report_data(self):
        self.ensure_one()
        res = self.sudo().read()
        move_lines = self.prepare_data()
        return {
            'form': res and res[0] or {},
            'date_start': self.date_start,
            'date_end': self.date_end,
            'ids': self.ids,
            'partner_name': self.partner_id.name,
            'partner_language': self.partner_id.lang,
            'item_lines': move_lines['item_lines'],
            'item_lines_invoices': move_lines["item_lines_invoices"],
            'item_lines_refunds': move_lines["item_lines_refunds"],
            'item_lines_net': move_lines["item_lines_net"],
            'total_credit_refund': move_lines["total_credit_refund"],
            'current_balance': move_lines["current_balance"],
            'currency': move_lines["currency"],
            'amount_currency': move_lines["amount_currency"],
            'user_id': self.user_id.name
        }

    def action_print_pdf(self):
        data = self._prepare_report_data()
        return self.env.ref('customer_account_statement.action_report_report_partner_ledger').with_context(
            lang=self.partner_id.lang or 'en_US').report_action(self,
                                                                data=data)

    def action_view_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/customer_account_statement/view/%s' % self.id,
            'target': 'new',
        }

    def action_download(self):
        if self.type == 'xlsx':
            return self.action_download_customer_account_statement()
        else:
            return self.action_print_pdf()
