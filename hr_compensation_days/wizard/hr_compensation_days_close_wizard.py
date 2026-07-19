# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class HrCompensationDaysCloseWizard(models.TransientModel):
    _name = 'hr.compensation.days.close.wizard'
    _description = 'Close Shift Allowance Month Wizard'

    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) + relativedelta(day=31),
    )
    action = fields.Selection(
        selection=[('pay', 'Close and Pay'), ('carry_forward', 'Carry Forward')],
        string='Closing Type',
        required=True,
        default='pay',
    )
    payment_date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today,
        help='Payment date used on the balance closing record.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Branch',
        required=True,
        default=lambda self: self.env.company,
        help='Close balances for this branch/company. Select employees to close only specific employees.',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Optional department scope inside the selected branch/company.',
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        help='Leave empty to include all employees with a shift allowance balance.',
    )
    line_ids = fields.One2many(
        'hr.compensation.days.close.wizard.line',
        'wizard_id',
        string='Employees Balances',
    )
    notes = fields.Text(string='Notes')

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from and (not self.date_to or self.date_to < self.date_from):
            self.date_to = self.date_from + relativedelta(day=31)

    def action_load_balances(self):
        self.ensure_one()
        self._check_dates()
        employee_domain = [('company_id', '=', self.company_id.id)]
        if self.department_id:
            employee_domain.append(('department_id', 'child_of', self.department_id.id))
        if self.employee_ids:
            employee_domain.append(('id', 'in', self.employee_ids.ids))
        employees = self.env['hr.employee'].search(employee_domain)
        commands = [(5, 0, 0)]
        for employee in employees:
            balance_days, balance_hours, balance_amount = self._get_employee_balance(employee)
            if (
                float_compare(balance_days, 0.0, precision_digits=2) > 0
                or float_compare(balance_hours, 0.0, precision_digits=2) > 0
                or float_compare(balance_amount, 0.0, precision_digits=2) > 0
            ):
                contract = self._get_employee_contract(employee)
                daily_wage = self._get_contract_daily_wage(contract)
                configured_unit, coefficient, hours_coefficient = self._get_employee_allowance_config(employee)
                commands.append((0, 0, {
                    'employee_id': employee.id,
                    'contract_id': contract.id if contract else False,
                    'balance_days': balance_days,
                    'balance_hours': balance_hours,
                    'balance_amount': balance_amount,
                    'rate': daily_wage,
                    'hourly_rate': daily_wage / 8.0 if daily_wage else 0.0,
                    'configured_allowance_unit': configured_unit,
                    'allowance_coefficient': coefficient,
                    'hours_allowance_coefficient': hours_coefficient,
                }))
        self.line_ids = commands
        return self._reopen_wizard()

    def action_close_month(self):
        self.ensure_one()
        self._check_dates()
        if not self.line_ids:
            self.action_load_balances()
        valid_lines = self.line_ids.filtered(lambda line: float_compare(line.balance_days, 0.0, precision_digits=2) > 0 or float_compare(line.balance_hours, 0.0, precision_digits=2) > 0 or float_compare(line.balance_amount, 0.0, precision_digits=2) > 0)
        if not valid_lines:
            raise UserError(_('There are no positive shift allowance days, hours, or amount balances to close.'))

        self._check_duplicate_paid_closing(valid_lines.employee_id)
        closing = self.env['hr.compensation.days.close'].create({
            'name': self._get_closing_name(),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company_id.id,
            'employee_id': valid_lines.employee_id.id if len(valid_lines.employee_id) == 1 else False,
            'department_id': self.department_id.id if self.department_id else False,
            'action': self.action,
            'payment_date': self.payment_date if self.action == 'pay' else False,
            'notes': self.notes,
        })
        for line in valid_lines:
            generated_entry = False
            if self.action == 'pay':
                generated_entry = self._create_spend_entries(line, closing)
            self.env['hr.compensation.days.close.line'].create({
                'closing_id': closing.id,
                'employee_id': line.employee_id.id,
                'balance_days': line.balance_days,
                'balance_hours': line.balance_hours,
                'balance_amount': line.balance_amount,
                'contract_id': line.contract_id.id if line.contract_id else False,
                'configured_allowance_unit': line.configured_allowance_unit,
                'allowance_coefficient': line.allowance_coefficient,
                'hours_allowance_coefficient': line.hours_allowance_coefficient,
                'rate': line.rate,
                'hourly_rate': line.hourly_rate,
                'days_amount': line.days_amount,
                'hours_amount': line.hours_amount,
                'mission_amount': line.mission_amount,
                'amount': line.amount,
                'generated_entry_id': generated_entry.id if generated_entry else False,
            })
        if self.env.context.get('print_close_xlsx_report'):
            return self._print_closing_xlsx_report(closing)
        if self.env.context.get('print_close_report'):
            return self._print_closing_report(closing)
        return self._get_closing_success_action()

    def action_close_month_and_print(self):
        self.ensure_one()
        return self.with_context(print_close_report=True).action_close_month()

    def action_close_month_and_export_xlsx(self):
        self.ensure_one()
        return self.with_context(print_close_xlsx_report=True).action_close_month()

    def _print_closing_report(self, closing):
        return self.env.ref(
            'hr_compensation_days.action_report_close_shift_allowance_month'
        ).report_action(closing)

    def _print_closing_xlsx_report(self, closing):
        return self.env.ref(
            'hr_compensation_days.action_report_close_shift_allowance_month_xlsx'
        ).report_action(closing)

    def _get_closing_success_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shift Allowance'),
                'message': _('Shift allowance balance has been closed successfully.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _create_spend_entries(self, line, closing):
        generated_entry = self.env['hr.compensation.days']
        common_values = {
            'employee_id': line.employee_id.id,
            'company_id': self.company_id.id,
            'date': self.date_to,
            'operation_type': 'spend',
            'notes': _('Shift allowance balance closing: %s') % closing.name,
            'state': 'confirmed',
            'closing_id': closing.id,
        }
        if float_compare(line.balance_days, 0.0, precision_digits=2) > 0:
            generated_entry = self.env['hr.compensation.days'].create({
                **common_values,
                'allowance_unit': 'day',
                'day_count': line.balance_days,
            })
        if float_compare(line.balance_hours, 0.0, precision_digits=2) > 0:
            hour_entry = self.env['hr.compensation.days'].create({
                **common_values,
                'allowance_unit': 'hour',
                'hour_count': line.balance_hours,
            })
            generated_entry = generated_entry or hour_entry
        if float_compare(line.balance_amount, 0.0, precision_digits=2) > 0:
            amount_entry = self.env['hr.compensation.days'].create({
                **common_values,
                'allowance_unit': 'amount',
                'amount': line.balance_amount,
            })
            generated_entry = generated_entry or amount_entry
        return generated_entry[:1]

    def _get_employee_balance(self, employee):
        grouped_data = self.env['hr.compensation.days'].read_group(
            domain=[
                ('employee_id', '=', employee.id),
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'confirmed'),
                ('date', '<=', self.date_to),
            ],
            fields=['balance_effect:sum', 'hour_balance_effect:sum', 'amount_balance_effect:sum'],
            groupby=[],
        )
        if not grouped_data:
            return 0.0, 0.0, 0.0
        return grouped_data[0].get('balance_effect', 0.0), grouped_data[0].get('hour_balance_effect', 0.0), grouped_data[0].get('amount_balance_effect', 0.0)

    def _get_employee_allowance_config(self, employee):
        coefficients = self.env['hr.shift.allowance.config'].get_department_coefficients(employee.department_id, self.company_id)
        configured_unit = 'hour' if coefficients.get('hour', 1.0) != 1.0 else 'shift'
        return configured_unit, coefficients.get('shift', 1.0), coefficients.get('hour', 1.0)

    def _get_employee_contract(self, employee):
        contract = employee.contract_id
        if contract and contract.state == 'open':
            return contract
        return self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', self.date_to),
            '|', ('date_end', '=', False), ('date_end', '>=', self.date_to),
        ], order='date_start desc, id desc', limit=1)

    def _get_contract_daily_wage(self, contract):
        if not contract:
            return 0.0
        if 'cost_per_day' in contract._fields and contract.cost_per_day:
            return contract.cost_per_day
        monthly_wage = contract.total if 'total' in contract._fields else contract.wage
        return monthly_wage / 30.0 if monthly_wage else 0.0

    def _get_closing_name(self):
        action_label = dict(self._fields['action'].selection).get(self.action)
        return '%s %s - %s' % (action_label, self.date_from, self.date_to)

    def _check_dates(self):
        if self.date_from > self.date_to:
            raise ValidationError(_('Date From must be before Date To.'))

    def _check_duplicate_paid_closing(self, employees):
        duplicate_domain = [
            ('state', '=', 'done'),
            ('action', '=', 'pay'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
            ('company_id', '=', self.company_id.id),
            ('line_ids.employee_id', 'in', employees.ids),
        ]
        if self.action == 'pay' and self.env['hr.compensation.days.close'].search_count(duplicate_domain):
            raise ValidationError(_('A paid balance closing already exists for one or more selected employees in this period.'))

    def _reopen_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Close Shift Allowance Month'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'dialog_size': 'large'},
        }


class HrCompensationDaysCloseWizardLine(models.TransientModel):
    _name = 'hr.compensation.days.close.wizard.line'
    _description = 'Close Shift Allowance Month Wizard Line'

    wizard_id = fields.Many2one(
        'hr.compensation.days.close.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, readonly=True)
    balance_days = fields.Float(string='Balance Days', readonly=True)
    balance_hours = fields.Float(string='Balance Hours', readonly=True)
    balance_amount = fields.Float(string='Balance Amount', readonly=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True)
    configured_allowance_unit = fields.Selection([('shift', 'Shift'), ('hour', 'Hours')], string='Configured Unit', readonly=True)
    allowance_coefficient = fields.Float(string='Days Coefficient', readonly=True, default=1.0)
    hours_allowance_coefficient = fields.Float(string='Hours Coefficient', readonly=True, default=1.0)
    rate = fields.Float(string='Daily Wage', readonly=True)
    hourly_rate = fields.Float(string='Hourly Wage', readonly=True)
    days_amount = fields.Float(string='Days Amount', compute='_compute_amount', store=True)
    hours_amount = fields.Float(string='Hours Amount', compute='_compute_amount', store=True)
    mission_amount = fields.Float(string='Mission Amount', compute='_compute_amount', store=True)
    amount = fields.Float(string='Total Amount', compute='_compute_amount', store=True)

    @api.depends('balance_days', 'balance_hours', 'balance_amount', 'rate', 'hourly_rate', 'allowance_coefficient', 'hours_allowance_coefficient')
    def _compute_amount(self):
        for line in self:
            days_coefficient = line.allowance_coefficient or 1.0
            hours_coefficient = line.hours_allowance_coefficient or 1.0
            line.days_amount = line.balance_days * line.rate * days_coefficient
            line.hours_amount = line.balance_hours * line.hourly_rate * hours_coefficient
            line.mission_amount = line.balance_amount
            line.amount = line.days_amount + line.hours_amount + line.mission_amount
