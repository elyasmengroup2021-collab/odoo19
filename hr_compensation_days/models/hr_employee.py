# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    compensation_days_balance = fields.Float(
        string='Shift Allowance Days Balance',
        compute='_compute_compensation_days_balance',
        help='Current confirmed shift allowance days balance.',
    )
    compensation_hours_balance = fields.Float(
        string='Shift Allowance Hours Balance',
        compute='_compute_compensation_days_balance',
        help='Current confirmed shift allowance hours balance.',
    )
    compensation_amount_balance = fields.Float(
        string='Shift Allowance Amount Balance',
        compute='_compute_compensation_days_balance',
        help='Current confirmed shift allowance amount balance.',
    )
    has_compensation_days = fields.Boolean(
        string='Has Shift Allowance Entries',
        compute='_compute_compensation_days_balance',
        search='_search_has_compensation_days',
    )

    @api.depends(
        'compensation_day_ids.state',
        'compensation_day_ids.operation_type',
        'compensation_day_ids.allowance_unit',
        'compensation_day_ids.day_count',
        'compensation_day_ids.hour_count',
        'compensation_day_ids.amount',
    )
    def _compute_compensation_days_balance(self):
        grouped_data = self.env['hr.compensation.days'].read_group(
            domain=[('employee_id', 'in', self.ids), ('state', '=', 'confirmed')],
            fields=['employee_id', 'balance_effect:sum', 'hour_balance_effect:sum', 'amount_balance_effect:sum'],
            groupby=['employee_id'],
        )
        balance_by_employee = {
            data['employee_id'][0]: data
            for data in grouped_data
        }
        employees_with_entries = set(self.env['hr.compensation.days'].search([
            ('employee_id', 'in', self.ids),
        ]).mapped('employee_id').ids)
        for employee in self:
            balance_data = balance_by_employee.get(employee.id, {})
            employee.compensation_days_balance = balance_data.get('balance_effect', 0.0)
            employee.compensation_hours_balance = balance_data.get('hour_balance_effect', 0.0)
            employee.compensation_amount_balance = balance_data.get('amount_balance_effect', 0.0)
            employee.has_compensation_days = employee.id in employees_with_entries

    def _search_has_compensation_days(self, operator, value):
        employee_ids = self.env['hr.compensation.days'].search([]).mapped('employee_id').ids
        if operator in ('=', '=='):
            has_entries = bool(value)
        elif operator in ('!=', '<>'):
            has_entries = not bool(value)
        else:
            has_entries = True
        return [('id', 'in' if has_entries else 'not in', employee_ids)]

    compensation_day_ids = fields.One2many(
        'hr.compensation.days',
        'employee_id',
        string='Shift Allowance Days',
    )
