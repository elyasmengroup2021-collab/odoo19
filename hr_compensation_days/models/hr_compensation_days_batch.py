# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class HrCompensationDaysBatch(models.Model):
    _name = 'hr.compensation.days.batch'
    _description = 'Daily Shift Allowance Days'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
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
    operation_type = fields.Selection(
        selection=[('add', 'Add Shift Allowance'), ('spend', 'Spend Shift Allowance'), ('mission', 'Mission')],
        string='Operation Type',
        required=True,
        default='add',
        tracking=True,
    )
    mission_type_id = fields.Many2one(
        'hr.compensation.days.mission.type',
        string='Mission Type',
        tracking=True,
        check_company=True,
    )
    line_ids = fields.One2many(
        'hr.compensation.days.batch.line',
        'batch_id',
        string='Employees',
        copy=True,
    )
    entry_ids = fields.One2many(
        'hr.compensation.days',
        'batch_id',
        string='Generated Entries',
        readonly=True,
    )
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    @api.onchange('mission_type_id')
    def _onchange_mission_type_id(self):
        for record in self:
            if record.operation_type == 'mission' and record.mission_type_id:
                for line in record.line_ids:
                    line.mission_type_id = record.mission_type_id
                    line.allowance_unit = record.mission_type_id.allowance_unit
                    line.day_count = record.mission_type_id.day_count
                    line.hour_count = record.mission_type_id.hour_count
                    line.amount = record.mission_type_id.amount

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if not values.get('line_ids'):
                raise ValidationError(_('Please add at least one employee line before saving.'))
            company = self._get_company_from_line_commands(values.get('line_ids'))
            if company:
                values['company_id'] = company.id
            if values.get('name', _('New')) == _('New'):
                values['name'] = self.env['ir.sequence'].next_by_code('hr.compensation.days.batch') or _('New')
        return super().create(vals_list)

    def write(self, values):
        if (
            any(record.state != 'draft' for record in self)
            and ({'date', 'company_id', 'operation_type', 'mission_type_id', 'line_ids'} & set(values))
            and not self.env.context.get('allow_shift_allowance_batch_update')
        ):
            raise UserError(_('You can only edit daily shift allowance lines while the batch is in draft.'))
        res = super().write(values)
        if 'line_ids' in values and 'company_id' not in values:
            for record in self.filtered(lambda batch: batch.state == 'draft'):
                company = record._get_company_from_lines()
                if company and record.company_id != company:
                    record.company_id = company.id
        return res

    def unlink(self):
        if any(record.entry_ids for record in self):
            raise UserError(_('You cannot delete a daily shift allowance batch after entries are generated.'))
        return super().unlink()

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            if not record.line_ids:
                raise ValidationError(_('Please add at least one employee line.'))
            record._check_not_in_closed_paid_period()
            record._check_batch_spend_balance()
            generated_entries = self.env['hr.compensation.days']
            for line in record.line_ids:
                entry = self.env['hr.compensation.days'].create({
                    'employee_id': line.employee_id.id,
                    'date': record.date,
                    'company_id': record.company_id.id,
                    'operation_type': record.operation_type,
                    'mission_type_id': record.mission_type_id.id,
                    'allowance_unit': line.allowance_unit,
                    'day_count': line.day_count,
                    'hour_count': line.hour_count,
                    'amount': line.amount,
                    'notes': line.notes or record.notes,
                    'state': 'draft',
                    'batch_id': record.id,
                })
                line.generated_entry_id = entry.id
                generated_entries |= entry
            generated_entries.with_context(allow_shift_allowance_batch_update=True).action_confirm()
            record.state = 'confirmed'

    def action_cancel(self):
        for record in self:
            if any(entry.closing_id for entry in record.entry_ids):
                raise UserError(_('You cannot cancel a batch that has entries generated from a balance closing.'))
            record.entry_ids.filtered(lambda entry: entry.state == 'confirmed').with_context(allow_shift_allowance_batch_update=True).action_cancel()
            record.state = 'cancelled'

    def action_reset_to_draft(self):
        for record in self:
            if record.entry_ids:
                raise UserError(_('You cannot reset a batch to draft after shift allowance entries are generated.'))
            record.state = 'draft'

    def _check_not_in_closed_paid_period(self):
        for record in self:
            employee_ids = record.line_ids.mapped('employee_id').ids
            if not employee_ids:
                continue
            paid_closing = self.env['hr.compensation.days.close'].search_count([
                ('state', '=', 'done'),
                ('action', '=', 'pay'),
                ('date_from', '<=', record.date),
                ('date_to', '>=', record.date),
                ('line_ids.employee_id', 'in', employee_ids),
            ])
            if paid_closing:
                raise ValidationError(_('You cannot add or modify shift allowance days or hours in a paid closed period.'))

    def _check_batch_spend_balance(self):
        for record in self:
            employee_ids = record.line_ids.mapped('employee_id').ids
            if not employee_ids:
                continue
            grouped_data = self.env['hr.compensation.days'].read_group(
                domain=[('employee_id', 'in', employee_ids), ('company_id', '=', record.company_id.id), ('state', '=', 'confirmed')],
                fields=['employee_id', 'balance_effect:sum', 'hour_balance_effect:sum', 'amount_balance_effect:sum'],
                groupby=['employee_id'],
            )
            balances = {
                data['employee_id'][0]: {
                    'day': data.get('balance_effect', 0.0),
                    'hour': data.get('hour_balance_effect', 0.0),
                    'amount': data.get('amount_balance_effect', 0.0),
                }
                for data in grouped_data
            }
            for employee in record.line_ids.mapped('employee_id'):
                balances.setdefault(employee.id, {'day': 0.0, 'hour': 0.0, 'amount': 0.0})
            for line in record.line_ids:
                sign = -1 if record.operation_type == 'spend' else 1
                if line.allowance_unit == 'day':
                    balances[line.employee_id.id]['day'] += sign * line.day_count
                elif line.allowance_unit == 'hour':
                    balances[line.employee_id.id]['hour'] += sign * line.hour_count
                else:
                    balances[line.employee_id.id]['amount'] += sign * line.amount
            for line in record.line_ids:
                employee_balance = balances[line.employee_id.id]
                if float_compare(employee_balance['day'], 0.0, precision_digits=2) < 0:
                    raise ValidationError(_('%s does not have enough shift allowance days balance.') % line.employee_id.name)
                if float_compare(employee_balance['hour'], 0.0, precision_digits=2) < 0:
                    raise ValidationError(_('%s does not have enough shift allowance hours balance.') % line.employee_id.name)
                if float_compare(employee_balance['amount'], 0.0, precision_digits=2) < 0:
                    raise ValidationError(_('%s does not have enough shift allowance amount balance.') % line.employee_id.name)

    @api.model
    def _get_company_from_line_commands(self, commands):
        employee_ids = []
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue
            command_type = command[0]
            if command_type == 0 and command[2].get('employee_id'):
                employee_ids.append(command[2]['employee_id'])
            elif command_type in (1, 4) and command[1]:
                line = self.env['hr.compensation.days.batch.line'].browse(command[1])
                if line.employee_id:
                    employee_ids.append(line.employee_id.id)
        companies = self.env['hr.employee'].browse(employee_ids).mapped('company_id')
        return companies[:1] if len(companies) == 1 else self.env['res.company']

    def _get_company_from_lines(self):
        self.ensure_one()
        companies = self.line_ids.mapped('employee_id.company_id')
        if len(companies) == 1:
            return companies
        entry_companies = self.entry_ids.mapped('company_id')
        if len(entry_companies) == 1:
            return entry_companies
        return self.env['res.company']

    @api.model
    def _fix_company_from_lines(self):
        for batch in self.search([]):
            company = batch._get_company_from_lines()
            if company and batch.company_id != company:
                batch.with_context(
                    allow_shift_allowance_batch_update=True,
                    tracking_disable=True,
                ).company_id = company.id
        return True

    @api.model
    def _get_company_from_line_commands(self, commands):
        employee_ids = []
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue
            command_type = command[0]
            if command_type == 0 and command[2].get('employee_id'):
                employee_ids.append(command[2]['employee_id'])
            elif command_type in (1, 4) and command[1]:
                line = self.env['hr.compensation.days.batch.line'].browse(command[1])
                if line.employee_id:
                    employee_ids.append(line.employee_id.id)
        companies = self.env['hr.employee'].browse(employee_ids).mapped('company_id')
        return companies[:1] if len(companies) == 1 else self.env['res.company']

    def _get_company_from_lines(self):
        self.ensure_one()
        companies = self.line_ids.mapped('employee_id.company_id')
        if len(companies) == 1:
            return companies
        entry_companies = self.entry_ids.mapped('company_id')
        if len(entry_companies) == 1:
            return entry_companies
        return self.env['res.company']

    @api.model
    def _fix_company_from_lines(self):
        for batch in self.search([]):
            company = batch._get_company_from_lines()
            if company and batch.company_id != company:
                batch.with_context(
                    allow_shift_allowance_batch_update=True,
                    tracking_disable=True,
                ).company_id = company.id
        return True


class HrCompensationDaysBatchLine(models.Model):
    _name = 'hr.compensation.days.batch.line'
    _description = 'Daily Shift Allowance Employee Line'
    _order = 'batch_id, id'

    batch_id = fields.Many2one(
        'hr.compensation.days.batch',
        string='Daily Shift Allowance',
        required=True,
        ondelete='cascade',
    )
    date = fields.Date(related='batch_id.date', string='Date', store=True, readonly=True)
    company_id = fields.Many2one(related='batch_id.company_id', string='Company', store=True, readonly=True)
    mission_type_id = fields.Many2one(
        'hr.compensation.days.mission.type',
        string='Mission Type',
        check_company=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
    )
    allowance_unit = fields.Selection(
        selection=[('day', 'Days'), ('hour', 'Hours'), ('amount', 'Amount')],
        string='Allowance Unit',
        required=True,
        default='day',
    )
    day_count = fields.Float(string='Days', required=True, default=1.0)
    hour_count = fields.Float(string='Hours', required=True, default=1.0)
    amount = fields.Float(string='Amount', required=True, default=1.0)
    current_days_balance = fields.Float(
        string='Current Days Balance',
        related='employee_id.compensation_days_balance',
        readonly=True,
    )
    current_hours_balance = fields.Float(
        string='Current Hours Balance',
        related='employee_id.compensation_hours_balance',
        readonly=True,
    )
    current_amount_balance = fields.Float(
        string='Current Amount Balance',
        related='employee_id.compensation_amount_balance',
        readonly=True,
    )
    resulting_days_balance = fields.Float(
        string='Resulting Days Balance',
        compute='_compute_resulting_balances',
    )
    resulting_hours_balance = fields.Float(
        string='Resulting Hours Balance',
        compute='_compute_resulting_balances',
    )
    resulting_amount_balance = fields.Float(
        string='Resulting Amount Balance',
        compute='_compute_resulting_balances',
    )
    generated_entry_id = fields.Many2one(
        'hr.compensation.days',
        string='Generated Entry',
        readonly=True,
        copy=False,
    )
    notes = fields.Char(string='Notes')

    @api.onchange('mission_type_id')
    def _onchange_mission_type_id(self):
        for line in self:
            if line.mission_type_id:
                line.allowance_unit = line.mission_type_id.allowance_unit
                line.day_count = line.mission_type_id.day_count
                line.hour_count = line.mission_type_id.hour_count
                line.amount = line.mission_type_id.amount

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(line.batch_id.state != 'draft' for line in records):
            raise UserError(_('You can only add employee lines while the batch is in draft.'))
        for line in records.filtered(lambda batch_line: batch_line.employee_id.company_id):
            batch = line.batch_id
            employee_company = line.employee_id.company_id
            if batch.state == 'draft' and batch.company_id != employee_company:
                batch.company_id = employee_company.id
        return records

    def write(self, values):
        if any(line.batch_id.state != 'draft' for line in self):
            raise UserError(_('You can only edit employee lines while the batch is in draft.'))
        res = super().write(values)
        if 'employee_id' in values:
            for line in self.filtered(lambda batch_line: batch_line.employee_id.company_id):
                batch = line.batch_id
                employee_company = line.employee_id.company_id
                if batch.state == 'draft' and batch.company_id != employee_company:
                    batch.company_id = employee_company.id
        return res

    def unlink(self):
        if any(line.batch_id.state != 'draft' for line in self):
            raise UserError(_('You can only delete employee lines while the batch is in draft.'))
        return super().unlink()

    @api.depends('employee_id', 'batch_id.operation_type', 'allowance_unit', 'day_count', 'hour_count', 'amount')
    def _compute_resulting_balances(self):
        for line in self:
            days_balance = line.current_days_balance
            hours_balance = line.current_hours_balance
            amount_balance = line.current_amount_balance
            sign = -1 if line.batch_id.operation_type == 'spend' else 1
            if line.allowance_unit == 'day':
                days_balance += sign * line.day_count
            elif line.allowance_unit == 'hour':
                hours_balance += sign * line.hour_count
            else:
                amount_balance += sign * line.amount
            line.resulting_days_balance = days_balance
            line.resulting_hours_balance = hours_balance
            line.resulting_amount_balance = amount_balance

    @api.constrains('day_count', 'hour_count', 'amount')
    def _check_quantity(self):
        for line in self:
            if float_compare(line.day_count, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_('Days must be greater than zero.'))
            if float_compare(line.hour_count, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_('Hours must be greater than zero.'))
            if float_compare(line.amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))
