import base64
import io

from odoo import fields, http
from odoo.http import request


class CustomerStatementController(http.Controller):

    @http.route(
        '/customer_account_statement/view/<int:wizard_id>',
        type='http',
        auth='user',
        methods=['GET'],
        website=False,
    )
    def view_customer_statement(self, wizard_id, **kwargs):
        wizard = request.env['customer.statement.wizard'].sudo().browse(wizard_id)
        if not wizard.exists():
            return request.not_found()

        move_lines = wizard.prepare_data()
        data = {
            'date_start': str(wizard.date_start),
            'date_end': str(wizard.date_end),
            'partner_name': wizard.partner_id.name,
            'partner_language': wizard.partner_id.lang or 'en_US',
            'item_lines': move_lines['item_lines'],
            'item_lines_invoices': move_lines['item_lines_invoices'],
            'item_lines_refunds': move_lines['item_lines_refunds'],
            'item_lines_net': move_lines['item_lines_net'],
            'total_credit_refund': move_lines['total_credit_refund'],
            'current_balance': move_lines['current_balance'],
            'currency': move_lines['currency'],
            'amount_currency': move_lines['amount_currency'],
            'user_id': wizard.user_id.name,
        }

        report = request.env.ref(
            'customer_account_statement.action_report_report_partner_ledger'
        ).with_context(lang=wizard.partner_id.lang or 'en_US')

        html_content = report._render_qweb_html(
            report.report_name,
            wizard.ids,
            data=data,
        )[0]

        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')],
        )

    @http.route(
        '/customer_account_statement/download/xlsx/<int:partner_id>/<date_start>/<date_end>',
        type='http',
        auth='user',
        methods=['GET'],
    )
    def download_xlsx(self, partner_id, date_start, date_end, **kwargs):
        import xlsxwriter
        wizard = request.env['customer.statement.wizard'].create({
            'partner_id': partner_id,
            'date_start': fields.Date.to_date(date_start),
            'date_end': fields.Date.to_date(date_end),
            'type': 'xlsx',
        })
        partner = request.env['res.partner'].browse(partner_id)
        if not partner.exists():
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False})
        title_style = workbook.add_format({'font_name': 'Times', 'font_size': 16, 'bold': True, 'align': 'center'})
        header_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#071f75', 'font_size': 14, 'color': 'white',
            'bold': True, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center',
        })
        text_style = workbook.add_format({
            'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left',
        })
        invoice_text_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#dac711', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left',
        })
        invoice_number_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#dac711', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center',
        })
        text_style_1 = workbook.add_format({
            'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center',
        })
        number_style = workbook.add_format({
            'font_name': 'Times', 'font_size': 12, 'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center',
        })
        refund_number_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#da5b11', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'center',
        })
        refund_text_style = workbook.add_format({
            'font_name': 'Times', 'fg_color': '#da5b11', 'font_size': 12,
            'left': 1, 'bottom': 1, 'right': 1, 'top': 1, 'align': 'left',
        })

        sheet = workbook.add_worksheet(name=u'كشف حساب عميل-{}'.format(partner.name))
        sheet.set_default_row(25)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 25)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 25)
        sheet.merge_range('A1:M1', u'كشف حســاب عميل : {}'.format(partner.name), title_style)
        sheet.write(2, 0, u'التاريخ', header_style)
        sheet.write(2, 1, u'اسم العميل', header_style)
        sheet.write(2, 2, u'البيان', header_style)
        sheet.write(2, 3, u'اسم الصنف', header_style)
        sheet.write(2, 4, u'ك. بالطن', header_style)
        sheet.write(2, 5, u'ك. بالشيكارة ', header_style)
        sheet.write(2, 6, u'س. الطن', header_style)
        sheet.write(2, 7, u'س. الشيكارة', header_style)
        sheet.write(2, 8, u'الخصم', header_style)
        sheet.write(2, 9, u'قيمة', header_style)
        sheet.write(2, 10, u'الاجمالى', header_style)
        sheet.write(2, 11, u'المسـدد', header_style)
        sheet.write(2, 12, u'الرصيد', header_style)

        aml_obj = request.env['account.move.line']
        start_balance_aml_ids = aml_obj.search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('partner_id', '=', partner.id),
            ('move_id.state', '=', 'posted'),
            ('date', '<', date_start),
        ])
        start_balance = sum(l.balance for l in start_balance_aml_ids)
        row = 3
        number = 1
        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1), u'رصــيد أول المــدة', text_style_1)
        for col in range(4, 12):
            sheet.write(row, col, 0, number_style)
        sheet.write(row, 12, start_balance, number_style)
        row += 1
        number += 1

        total_t = []
        total_shikara = []
        total_sale_refund_amount = []
        amls = aml_obj.search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('partner_id', '=', partner.id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_start),
            ('date', '<=', date_end),
        ], order='date ASC')

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
                            if line.product_uom_id.name in ('kg', u'كجم'):
                                n_o_tons = line.quantity / 1000
                            if line.product_uom_id.name in ('t', u'طن'):
                                t = line.quantity
                            qty_tons = n_o_tons if n_o_tons > 0.0 else t
                            unit_price = line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit
                            total_amount = qty_tons * unit_price - (qty_tons * unit_price * line.discount / 100)
                            start_balance += total_amount
                            sheet.write(row, 0, fields.Date.to_string(sale_aml.date) if sale_aml.date else ' ', invoice_text_style)
                            sheet.write(row, 1, sale_aml.partner_id.name, invoice_text_style)
                            sheet.write(row, 2, u'Sales: %s' % (sale_aml.name if sale_aml.name else sale_aml.ref), invoice_text_style)
                            sheet.write(row, 3, line.product_id.name or False, invoice_text_style)
                            total_t.append(qty_tons)
                            sheet.write(row, 4, n_o_tons if n_o_tons > 0.0 else t, invoice_number_style)
                            total_shikara.append(qty_tons * no_bags)
                            sheet.write(row, 5, qty_tons * no_bags, invoice_number_style)
                            sheet.write(row, 6, line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit, invoice_number_style)
                            sheet.write(row, 7, (line.price_unit * 1000) / no_bags if n_o_tons > 0.0 else line.price_unit / no_bags, invoice_number_style)
                            sheet.write(row, 8, line.discount or 0, invoice_number_style)
                            total_sale_refund_amount.append(total_amount)
                            sheet.write(row, 9, total_amount, invoice_number_style)
                            sheet.write(row, 10, total_amount, invoice_number_style)
                            sheet.write(row, 11, 0, invoice_number_style)
                            sheet.write(row, 12, round(start_balance, 2), invoice_number_style)
                            row += 1
                            number += 1

            payment_amls = amls.filtered(lambda aml: aml.payment_id)
            if payment_amls:
                for payments_aml in payment_amls:
                    start_balance -= payments_aml.credit if payments_aml.payment_id else 0
                    sheet.write(row, 0, fields.Date.to_string(payments_aml.date) if payments_aml.date else ' ', text_style)
                    sheet.write(row, 1, payments_aml.partner_id.name, text_style)
                    sheet.write(row, 2, payments_aml.ref if payments_aml.ref else payments_aml.name, text_style)
                    sheet.write(row, 3, payments_aml.product_id.name or ' ', text_style)
                    for col in range(4, 11):
                        sheet.write(row, col, 0, number_style)
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
                            if line.product_uom_id.name in ('kg', u'كجم'):
                                n_o_tons = line.quantity / 1000
                            if line.product_uom_id.name in ('t', u'طن'):
                                t = line.quantity
                            qty_tons = n_o_tons if n_o_tons > 0.0 else t
                            unit_price = line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit
                            total_amount = qty_tons * unit_price - (qty_tons * unit_price * line.discount / 100)
                            start_balance -= total_amount
                            sheet.write(row, 0, fields.Date.to_string(refunds_aml.date) if refunds_aml.date else ' ', refund_text_style)
                            sheet.write(row, 1, refunds_aml.partner_id.name, refund_text_style)
                            sheet.write(row, 2, u'مرتجعـــات:{}'.format(item.name if item.name else item.ref), refund_text_style)
                            sheet.write(row, 3, line.product_id.name or False, refund_text_style)
                            total_t.append(-1 * qty_tons)
                            sheet.write(row, 4, n_o_tons if n_o_tons > 0.0 else t, refund_number_style)
                            total_shikara.append(-1 * qty_tons * no_bags)
                            sheet.write(row, 5, qty_tons * no_bags, refund_number_style)
                            sheet.write(row, 6, line.price_unit * 1000 if n_o_tons > 0.0 else line.price_unit, refund_number_style)
                            sheet.write(row, 7, (line.price_unit * 1000) / no_bags if n_o_tons > 0.0 else line.price_unit / no_bags, refund_number_style)
                            sheet.write(row, 8, line.discount or 0, refund_number_style)
                            total_sale_refund_amount.append(-1 * total_amount)
                            sheet.write(row, 9, total_amount, refund_number_style)
                            sheet.write(row, 10, total_amount, refund_number_style)
                            sheet.write(row, 11, 0, refund_number_style)
                            sheet.write(row, 12, round(start_balance, 2), refund_number_style)
                            row += 1
                            number += 1

        sheet.merge_range('A' + str(row + 1) + ':D' + str(row + 1), 'Total', header_style)
        sheet.write(row, 4, sum(total_t), header_style)
        sheet.write(row, 5, sum(total_shikara), header_style)
        for col in range(6, 9):
            sheet.write(row, col, 0, header_style)
        sheet.write(row, 9, sum(total_sale_refund_amount), header_style)
        sheet.write(row, 10, sum(total_sale_refund_amount), header_style)
        sheet.write_formula(row, 11, '=SUM(L5:L' + str(row) + ')', header_style)
        sheet.write_formula(row, 12, '=M' + str(row), header_style)
        workbook.close()
        output.seek(0)

        content = base64.b64encode(output.read())
        output.close()

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="Customer_Statement_%s.xlsx"' % partner.name),
            ],
        )
