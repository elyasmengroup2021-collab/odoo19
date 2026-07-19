# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class HrCompensationDays(models.Model):
    _name = 'hr.compensation.days'
    _description = 'HR Shift Allowance Day'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Sequence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
        index=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    operation_type = fields.Selection(
        selection=[('add', 'Add Shift Allowance'), ('spend', 'Spend Shift Allowance'), ('mission', 'Mission')],
        string='Operation Type',
        required=True,
        default='add',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    mission_type_id = fields.Many2one(
        'hr.compensation.days.mission.type',
        string='Mission Type',
        tracking=True,
        check_company=True,
    )
    allowance_unit = fields.Selection(
        selection=[('day', 'Days'), ('hour', 'Hours'), ('amount', 'Amount')],
        string='Allowance Unit',
        required=True,
        default='day',
        tracking=True,
    )
    day_count = fields.Float(
        string='Days',
        required=True,
        default=1.0,
        tracking=True,
    )
    hour_count = fields.Float(
        string='Hours',
        required=True,
        default=1.0,
        tracking=True,
    )
    amount = fields.Float(
        string='Amount',
        required=True,
        default=1.0,
        tracking=True,
    )
    display_day_count = fields.Float(
        string='Days',
        compute='_compute_display_counts',
        store=True,
    )
    display_hour_count = fields.Float(
        string='Hours',
        compute='_compute_display_counts',
        store=True,
    )
    display_amount = fields.Float(
        string='Amount',
        compute='_compute_display_counts',
        store=True,
    )
    balance_effect = fields.Float(
        string='Days Balance Effect',
        compute='_compute_balance_effect',
        store=True,
    )
    hour_balance_effect = fields.Float(
        string='Hours Balance Effect',
        compute='_compute_balance_effect',
        store=True,
    )
    amount_balance_effect = fields.Float(
        string='Amount Balance Effect',
        compute='_compute_balance_effect',
        store=True,
    )
    balance_before = fields.Float(
        string='Days Balance Before',
        compute='_compute_balances',
    )
    balance_after = fields.Float(
        string='Days Balance After',
        compute='_compute_balances',
    )
    hour_balance_before = fields.Float(
        string='Hours Balance Before',
        compute='_compute_balances',
    )
    hour_balance_after = fields.Float(
        string='Hours Balance After',
        compute='_compute_balances',
    )
    amount_balance_before = fields.Float(
        string='Amount Balance Before',
        compute='_compute_balances',
    )
    amount_balance_after = fields.Float(
        string='Amount Balance After',
        compute='_compute_balances',
    )
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    closing_id = fields.Many2one(
        'hr.compensation.days.close',
        string='Balance Closing',
        readonly=True,
        copy=False,
    )
    batch_id = fields.Many2one(
        'hr.compensation.days.batch',
        string='Daily Shift Allowance Batch',
        readonly=True,
        copy=False,
    )
    closing_action = fields.Selection(
        related='closing_id.action',
        string='Closing Action',
        store=True,
        readonly=True,
    )
    _sql_constraints = [
        ('positive_day_count', 'CHECK(day_count > 0)', 'Days must be greater than zero.'),
        ('positive_hour_count', 'CHECK(hour_count > 0)', 'Hours must be greater than zero.'),
        ('positive_amount', 'CHECK(amount >= 0)', 'Amount must be zero or greater.')
    ]

    @api.depends('allowance_unit', 'day_count', 'hour_count', 'amount')
    def _compute_display_counts(self):
        for record in self:
            record.display_day_count = record.day_count if record.allowance_unit == 'day' else 0.0
            record.display_hour_count = record.hour_count if record.allowance_unit == 'hour' else 0.0
            record.display_amount = record.amount if record.allowance_unit == 'amount' else 0.0

    @api.depends('operation_type', 'allowance_unit', 'day_count', 'hour_count', 'amount')
    def _compute_balance_effect(self):
        for record in self:
            sign = -1 if record.operation_type == 'spend' else 1
            record.balance_effect = sign * record.day_count if record.allowance_unit == 'day' else 0.0
            record.hour_balance_effect = sign * record.hour_count if record.allowance_unit == 'hour' else 0.0
            record.amount_balance_effect = sign * record.amount if record.allowance_unit == 'amount' else 0.0

    @api.onchange('mission_type_id')
    def _onchange_mission_type_id(self):
        for record in self:
            if record.mission_type_id:
                record.allowance_unit = record.mission_type_id.allowance_unit
                record.day_count = record.mission_type_id.day_count
                record.hour_count = record.mission_type_id.hour_count
                record.amount = record.mission_type_id.amount

    @api.onchange('employee_id')
    def _onchange_employee_id_company(self):
        for record in self:
            if record.employee_id.company_id:
                record.company_id = record.employee_id.company_id

    @api.onchange('employee_id', 'date', 'operation_type', 'allowance_unit', 'day_count', 'hour_count', 'amount', 'state')
    def _onchange_balance_fields(self):
        self._compute_balance_effect()
        self._compute_balances()

    @api.depends('employee_id', 'date', 'state', 'balance_effect', 'hour_balance_effect', 'amount_balance_effect')
    def _compute_balances(self):
        for record in self:
            if not record.employee_id or not record.date:
                record.balance_before = 0.0
                record.balance_after = 0.0
                record.hour_balance_before = 0.0
                record.hour_balance_after = 0.0
                record.amount_balance_before = 0.0
                record.amount_balance_after = 0.0
                continue
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('company_id', '=', record.company_id.id),
                ('state', '=', 'confirmed'),
                ('date', '<=', record.date),
            ]
            if record._origin.id:
                domain.append(('id', '!=', record._origin.id))
            grouped_data = self.read_group(domain, ['balance_effect:sum', 'hour_balance_effect:sum', 'amount_balance_effect:sum'], [])
            balance_before = grouped_data[0].get('balance_effect', 0.0) if grouped_data else 0.0
            hour_balance_before = grouped_data[0].get('hour_balance_effect', 0.0) if grouped_data else 0.0
            record.balance_before = balance_before
            record.balance_after = balance_before + record.balance_effect
            record.hour_balance_before = hour_balance_before
            amount_balance_before = grouped_data[0].get('amount_balance_effect', 0.0) if grouped_data else 0.0
            record.hour_balance_after = hour_balance_before + record.hour_balance_effect
            record.amount_balance_before = amount_balance_before
            record.amount_balance_after = amount_balance_before + record.amount_balance_effect

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('employee_id'):
                employee = self.env['hr.employee'].browse(values['employee_id'])
                values['company_id'] = employee.company_id.id or self.env.company.id
            if values.get('name', _('New')) == _('New'):
                values['name'] = self.env['ir.sequence'].next_by_code('hr.compensation.days') or _('New')
        records = super().create(vals_list)
        records._check_not_in_closed_paid_period()
        records._check_spend_balance()
        return records

    def write(self, values):
        protected_fields = {'employee_id', 'company_id', 'date', 'operation_type', 'mission_type_id', 'allowance_unit', 'day_count', 'hour_count', 'amount', 'state'}
        if any(record.batch_id for record in self) and protected_fields & set(values) and not self.env.context.get('allow_shift_allowance_batch_update'):
            raise UserError(_('You cannot directly modify entries generated from a daily shift allowance batch.'))
        if values.get('employee_id') and 'company_id' not in values:
            employee = self.env['hr.employee'].browse(values['employee_id'])
            values['company_id'] = employee.company_id.id or self.env.company.id
        res = super().write(values)
        if (
            {'employee_id', 'company_id', 'date', 'operation_type', 'mission_type_id', 'allowance_unit', 'day_count', 'hour_count', 'amount', 'state'} & set(values)
            and not self.env.context.get('skip_shift_allowance_balance_check')
        ):
            self._check_not_in_closed_paid_period()
            self._check_spend_balance()
        return res

    @api.model
    def _fix_company_from_employees(self):
        """Align existing shift allowance records with their employees' companies.

        This method is intentionally loaded from XML data so it runs during module
        upgrades and corrects records that were initially created with the active
        company instead of the employee/batch company.
        """
        entries = self.sudo().search([('employee_id.company_id', '!=', False)])
        for entry in entries:
            employee_company = entry.employee_id.company_id
            if entry.company_id != employee_company:
                entry.with_context(
                    allow_shift_allowance_batch_update=True,
                    skip_shift_allowance_balance_check=True,
                    tracking_disable=True,
                ).company_id = employee_company.id
        self.env['hr.compensation.days.batch'].sudo()._fix_company_from_lines()
        return True

    def unlink(self):
        if any(record.closing_id for record in self):
            raise UserError(_('You cannot delete records generated from a balance closing.'))
        if any(record.batch_id for record in self):
            raise UserError(_('You cannot delete entries generated from a daily shift allowance batch.'))
        return super().unlink()

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            record._check_not_in_closed_paid_period()
            record.state = 'confirmed'
        self._check_spend_balance()

    def action_reset_to_draft(self):
        if any(record.closing_id for record in self):
            raise UserError(_('You cannot reset records generated from a balance closing to draft.'))
        if any(record.batch_id for record in self) and not self.env.context.get('allow_shift_allowance_batch_update'):
            raise UserError(_('You cannot reset entries generated from a daily shift allowance batch to draft.'))
        self.write({'state': 'draft'})

    def action_cancel(self):
        if any(record.closing_id for record in self):
            raise UserError(_('You cannot cancel records generated from a balance closing.'))
        if any(record.batch_id for record in self) and not self.env.context.get('allow_shift_allowance_batch_update'):
            raise UserError(_('You cannot cancel entries generated from a daily shift allowance batch directly.'))
        self.write({'state': 'cancelled'})

    @api.constrains('day_count', 'hour_count', 'amount')
    def _check_quantity(self):
        for record in self:
            if float_compare(record.day_count, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_('Days must be greater than zero.'))
            if float_compare(record.hour_count, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_('Hours must be greater than zero.'))
            if float_compare(record.amount, 0.0, precision_digits=2) < 0:
                raise ValidationError(_('Amount must be zero or greater.'))

    @api.constrains('operation_type', 'allowance_unit', 'day_count', 'hour_count', 'amount', 'employee_id', 'state')
    def _check_spend_balance(self):
        if self.env.context.get('skip_shift_allowance_balance_check'):
            return
        for record in self.filtered(lambda rec: rec.state == 'confirmed' and rec.operation_type == 'spend'):
            grouped_data = self.read_group(
                domain=[('employee_id', '=', record.employee_id.id), ('company_id', '=', record.company_id.id), ('state', '=', 'confirmed')],
                fields=['balance_effect:sum', 'hour_balance_effect:sum', 'amount_balance_effect:sum'],
                groupby=[],
            )
            balance = grouped_data[0].get('balance_effect', 0.0) if grouped_data else 0.0
            hour_balance = grouped_data[0].get('hour_balance_effect', 0.0) if grouped_data else 0.0
            amount_balance = grouped_data[0].get('amount_balance_effect', 0.0) if grouped_data else 0.0
            if float_compare(balance, 0.0, precision_digits=2) < 0:
                raise ValidationError(_('The employee does not have enough shift allowance days balance.'))
            if float_compare(hour_balance, 0.0, precision_digits=2) < 0:
                raise ValidationError(_('The employee does not have enough shift allowance hours balance.'))
            if float_compare(amount_balance, 0.0, precision_digits=2) < 0:
                raise ValidationError(_('The employee does not have enough shift allowance amount balance.'))

    def _check_not_in_closed_paid_period(self):
        for record in self.filtered(lambda rec: rec.employee_id and rec.date and not rec.closing_id):
            paid_closing = self.env['hr.compensation.days.close'].search_count([
                ('state', '=', 'done'),
                ('action', '=', 'pay'),
                ('date_from', '<=', record.date),
                ('date_to', '>=', record.date),
                ('line_ids.employee_id', '=', record.employee_id.id),
            ])
            if paid_closing:
                raise ValidationError(_('You cannot add or modify shift allowance days or hours in a paid closed period.'))
