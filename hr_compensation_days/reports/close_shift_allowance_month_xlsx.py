# -*- coding: utf-8 -*-

from odoo import fields, models


class CloseShiftAllowanceMonthXlsx(models.AbstractModel):
    _name = 'report.hr_compensation_days.close_shift_allowance_month_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Close Shift Allowance Month XLSX Report'

    def generate_xlsx_report(self, workbook, data, closings):
        used_sheet_names = set()
        for closing in closings:
            sheet_name = self._get_unique_sheet_name(closing, used_sheet_names)
            self._generate_closing_sheet(workbook, closing, sheet_name)

    def _generate_closing_sheet(self, workbook, closing, sheet_name):
        sheet = workbook.add_worksheet(sheet_name)
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
        })
        label_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9E1F2'})
        value_format = workbook.add_format({'border': 1})
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D9E1F2',
        })
        text_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_label_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#E2F0D9'})
        total_number_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#E2F0D9', 'num_format': '#,##0.00'})

        sheet.merge_range(0, 0, 0, 11, 'Close Shift Allowance Month', title_format)
        sheet.write(2, 0, 'Reference', label_format)
        sheet.write(2, 1, closing.name or '', value_format)
        sheet.write(2, 2, 'Closing Type', label_format)
        sheet.write(2, 3, dict(closing._fields['action'].selection).get(closing.action, ''), value_format)
        sheet.write(3, 0, 'Branch', label_format)
        sheet.write(3, 1, closing.company_id.display_name or '', value_format)
        sheet.write(3, 2, 'Employee', label_format)
        sheet.write(3, 3, closing.employee_id.display_name or '', value_format)
        sheet.write(4, 0, 'Date From', label_format)
        sheet.write(4, 1, fields.Date.to_string(closing.date_from) if closing.date_from else '', value_format)
        sheet.write(4, 2, 'Date To', label_format)
        sheet.write(4, 3, fields.Date.to_string(closing.date_to) if closing.date_to else '', value_format)
        sheet.write(4, 4, 'Payment Date', label_format)
        sheet.write(4, 5, fields.Date.to_string(closing.payment_date) if closing.payment_date else '', value_format)

        headers = [
            'Employee',
            'Department',
            'Coefficient',
            'Balance Days',
            'Balance Hours',
            'Balance Amount',
            'Daily Wage',
            'Hourly Wage',
            'Days Amount',
            'Hours Amount',
            'Mission Amount',
            'Total Amount',
        ]
        header_row = 6
        for col, header in enumerate(headers):
            sheet.write(header_row, col, header, header_format)

        row = header_row + 1
        for line in closing.line_ids:
            sheet.write(row, 0, line.employee_id.display_name or '', text_format)
            sheet.write(row, 1, line.department_id.display_name or '', text_format)
            sheet.write_number(row, 2, line.allowance_coefficient, number_format)
            sheet.write_number(row, 3, line.balance_days, number_format)
            sheet.write_number(row, 4, line.balance_hours, number_format)
            sheet.write_number(row, 5, line.balance_amount, number_format)
            sheet.write_number(row, 6, line.rate, number_format)
            sheet.write_number(row, 7, line.hourly_rate, number_format)
            sheet.write_number(row, 8, line.days_amount, number_format)
            sheet.write_number(row, 9, line.hours_amount, number_format)
            sheet.write_number(row, 10, line.mission_amount, number_format)
            sheet.write_number(row, 11, line.amount, number_format)
            row += 1

        sheet.write(row, 0, 'Total', total_label_format)
        sheet.write_blank(row, 1, None, total_label_format)
        sheet.write_blank(row, 2, None, total_label_format)
        sheet.write_number(row, 3, sum(closing.line_ids.mapped('balance_days')), total_number_format)
        sheet.write_number(row, 4, sum(closing.line_ids.mapped('balance_hours')), total_number_format)
        sheet.write_number(row, 5, sum(closing.line_ids.mapped('balance_amount')), total_number_format)
        sheet.write_blank(row, 6, None, total_label_format)
        sheet.write_blank(row, 7, None, total_label_format)
        sheet.write_number(row, 8, sum(closing.line_ids.mapped('days_amount')), total_number_format)
        sheet.write_number(row, 9, sum(closing.line_ids.mapped('hours_amount')), total_number_format)
        sheet.write_number(row, 10, sum(closing.line_ids.mapped('mission_amount')), total_number_format)
        sheet.write_number(row, 11, sum(closing.line_ids.mapped('amount')), total_number_format)

        if closing.notes:
            row += 2
            sheet.write(row, 0, 'Notes', label_format)
            sheet.merge_range(row, 1, row, 11, closing.notes, value_format)

        sheet.set_column(0, 1, 28)
        sheet.set_column(2, 5, 16)
        sheet.set_column(6, 11, 18)
        sheet.freeze_panes(header_row + 1, 0)
        if closing.line_ids:
            sheet.autofilter(header_row, 0, row - (2 if closing.notes else 0), 11)

    def _get_unique_sheet_name(self, closing, used_sheet_names):
        name = closing.name or 'Closing'
        for char in ['[', ']', ':', '*', '?', '/', '\\']:
            name = name.replace(char, ' ')
        name = name[:31].strip() or 'Closing'
        sheet_name = name
        index = 1
        while sheet_name in used_sheet_names:
            suffix = ' %s' % index
            sheet_name = '%s%s' % (name[:31 - len(suffix)], suffix)
            index += 1
        used_sheet_names.add(sheet_name)
        return sheet_name
