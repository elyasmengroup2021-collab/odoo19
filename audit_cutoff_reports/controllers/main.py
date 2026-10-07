import io
import json

from odoo import http
from odoo.http import request, content_disposition


class AuditCutoffExportController(http.Controller):
    @http.route('/audit_cutoff_reports/export_xlsx_native', type='http', auth='user', methods=['GET'], csrf=False)
    def export_xlsx_native(self, session_key, domain='[]', group_by='[]', **kwargs):
        if not request.env.user.has_group('account.group_account_user'):
            return request.not_found()
        try:
            domain = json.loads(domain or '[]')
            group_by = json.loads(group_by or '[]')
        except Exception:
            return request.not_found()
        Line = request.env['account.cutoff.report.line'].sudo()
        base = [('session_key', '=', session_key), ('user_id', '=', request.env.user.id)]
        lines = Line.search(base + domain, order='partner_id,order_date,order_ref,id')
        if not lines:
            return request.not_found()
        report_type = lines[0].report_type
        title = dict(Line._fields['report_type'].selection).get(report_type, 'Audit Cut-off')
        as_of = lines[0].as_of_date
        purchase = report_type in ('bills_to_receive', 'billed_not_received')

        import xlsxwriter
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet('Audit Cut-off')
        sheet.freeze_panes(5, 0)
        title_fmt = workbook.add_format({'bold': True, 'font_size': 16})
        meta_fmt = workbook.add_format({'font_color': '#666666'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F1F1F1', 'border': 1, 'align': 'center'})
        text_fmt = workbook.add_format({'border': 1})
        num_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        money_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_fmt = workbook.add_format({'bold': True, 'top': 2, 'num_format': '#,##0.00'})
        group_fmt = workbook.add_format({'bold': True, 'bg_color': '#E8E8E8', 'top': 1})
        group_num_fmt = workbook.add_format({'bold': True, 'bg_color': '#E8E8E8', 'top': 1, 'num_format': '#,##0.00'})

        sheet.merge_range('A1:K1', title, title_fmt)
        sheet.write('A2', 'As of', meta_fmt)
        sheet.write('B2', str(as_of), meta_fmt)
        sheet.write('D2', 'Group By', meta_fmt)
        sheet.write('E2', ', '.join(group_by) if group_by else 'Partner', meta_fmt)
        sheet.write('G2', 'Rows', meta_fmt)
        sheet.write('H2', len(lines), meta_fmt)
        headers = ['Order Reference', 'Partner', 'Product', 'Description', 'Salesperson', 'Quantity', 'Received', 'Billed', 'Delivered', 'Invoiced', 'Unit', 'Unit Price', 'Amount']
        for col, header in enumerate(headers):
            sheet.write(4, col, header, header_fmt)

        row_idx = 5
        total_qty = total_amount = 0.0
        for line in lines:
            vals = [
                line.order_ref or '', line.partner_id.display_name or '', line.product_id.display_name or '',
                line.description or '', line.salesperson_id.display_name or '', line.quantity, line.received,
                line.billed, line.delivered, line.invoiced, line.uom_id.display_name or '', line.unit_price, line.amount,
            ]
            numeric = {5, 6, 7, 8, 9, 11, 12}
            for col, value in enumerate(vals):
                if col in numeric:
                    sheet.write_number(row_idx, col, float(value or 0), money_fmt if col == 12 else num_fmt)
                else:
                    sheet.write(row_idx, col, value, text_fmt)
            total_qty += line.quantity or 0
            total_amount += line.amount or 0
            row_idx += 1
        sheet.write(row_idx, 0, 'Grand Total', total_fmt)
        sheet.write_number(row_idx, 5, total_qty, total_fmt)
        sheet.write_number(row_idx, 12, total_amount, total_fmt)
        widths = [18, 24, 34, 32, 22, 12, 12, 12, 12, 12, 14, 14, 16]
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)
        workbook.close()
        content = buffer.getvalue()
        buffer.close()
        filename = f'{title} - {as_of}.xlsx'.replace('/', '-')
        return request.make_response(content, [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ])
