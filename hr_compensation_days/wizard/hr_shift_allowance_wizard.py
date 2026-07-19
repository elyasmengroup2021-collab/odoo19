# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrShiftAllowanceWizard(models.TransientModel):
    _name = 'hr.shift.allowance.wizard'
    _description = 'Add or Deduct Shift Allowance Wizard'

    employee_id = fields.Many2one('hr.employee', string='Employee Name', required=True, default=lambda self: self.env.user.employee_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one(related='employee_id.department_id', string='Department', readonly=True)
    date = fields.Date(string='Day', required=True, default=fields.Date.context_today)
    movement_type = fields.Selection([
        ('add', 'إضافة بدل وردية'),
        ('deduct', 'صرف بدل وردية'),
    ], string='Form Type', required=True, default='add')
    allowance_unit = fields.Selection([('shift', 'Shift'), ('hour', 'Hours')], string='Allowance Unit', default='shift', required=True)
    coefficient = fields.Float(string='Coefficient', default=1.0, required=True)
    input_quantity = fields.Float(string='Quantity / Hours', required=True, default=1.0)
    calculated_quantity = fields.Float(string='Calculated Balance Quantity', compute='_compute_calculated_quantity')
    current_balance = fields.Float(string='Balance', compute='_compute_current_balance')
    note = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_shift_allowance_wizard_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Attachments',
    )

    @api.depends('input_quantity', 'coefficient')
    def _compute_calculated_quantity(self):
        for wizard in self:
            wizard.calculated_quantity = wizard.input_quantity * wizard.coefficient

    @api.depends('employee_id', 'company_id')
    def _compute_current_balance(self):
        Line = self.env['hr.shift.allowance.line']
        for wizard in self:
            wizard.current_balance = wizard.employee_id and Line.get_employee_balance(wizard.employee_id.id, wizard.company_id.id) or 0.0

    @api.onchange('employee_id', 'company_id')
    def _onchange_employee_id(self):
        if self.employee_id.company_id:
            self.company_id = self.employee_id.company_id
        self._apply_department_config()

    def _apply_department_config(self):
        Config = self.env['hr.shift.allowance.config']
        for wizard in self:
            if not wizard.employee_id.department_id:
                wizard.allowance_unit = 'shift'
                wizard.coefficient = 1.0
                continue
            unit, coefficient = Config.get_department_config(wizard.employee_id.department_id, wizard.company_id)
            wizard.allowance_unit = unit
            wizard.coefficient = coefficient

    def action_apply(self):
        self.ensure_one()
        if self.input_quantity <= 0:
            raise UserError(_('Quantity / hours must be greater than zero.'))
        quantity = self.input_quantity * self.coefficient
        if self.movement_type == 'deduct' and quantity > self.current_balance:
            raise UserError(_('You cannot deduct more than the current shift allowance balance.'))
        line = self.env['hr.shift.allowance.line'].create({
            'employee_id': self.employee_id.id,
            'company_id': self.company_id.id,
            'date': self.date,
            'movement_type': self.movement_type,
            'allowance_unit': self.allowance_unit,
            'input_quantity': self.input_quantity,
            'coefficient': self.coefficient,
            'quantity': quantity,
            'note': self.note,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })
        self.attachment_ids.sudo().write({'res_model': 'hr.shift.allowance.line', 'res_id': line.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Allowance Movement'),
            'res_model': 'hr.shift.allowance.line',
            'view_mode': 'form',
            'res_id': line.id,
        }


class HrShiftAllowanceCloseWizard(models.TransientModel):
    _name = 'hr.shift.allowance.close.wizard'
    _description = 'Monthly Shift Allowance Closing Wizard'

    date_to = fields.Date(string='Closing Date', required=True, default=fields.Date.context_today)
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department', check_company=True)
    close_type = fields.Selection([
        ('pay', 'صرف وإغلاق الرصيد'),
        ('carry', 'ترحيل الرصيد للشهر التالي'),
    ], string='Closing Type', required=True, default='carry')
    note = fields.Text(string='Notes')

    def action_close_month(self):
        self.ensure_one()
        employee_domain = [('company_id', '=', self.company_id.id), ('active', '=', True)]
        if self.department_id:
            employee_domain.append(('department_id', '=', self.department_id.id))
        employees = self.employee_ids or self.env['hr.employee'].search(employee_domain)
        if self.employee_ids and self.department_id:
            employees = self.employee_ids.filtered(lambda employee: employee.department_id == self.department_id)
        close = self.env['hr.shift.allowance.close'].create({
            'company_id': self.company_id.id,
            'department_id': self.department_id.id if self.department_id else False,
            'date_to': self.date_to,
            'close_type': self.close_type,
            'note': self.note,
        })
        Line = self.env['hr.shift.allowance.line']
        if self.close_type == 'pay':
            for employee in employees:
                balance = Line.get_employee_balance(employee.id, self.company_id.id, self.date_to)
                if balance <= 0:
                    continue
                Line.create({
                    'employee_id': employee.id,
                    'company_id': self.company_id.id,
                    'date': self.date_to,
                    'movement_type': 'close_paid',
                    'allowance_unit': 'shift',
                    'input_quantity': balance,
                    'coefficient': 1.0,
                    'quantity': balance,
                    'note': self.note or _('Monthly paid closing'),
                    'is_monthly_close': True,
                    'close_id': close.id,
                })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Allowance Closing'),
            'res_model': 'hr.shift.allowance.close',
            'view_mode': 'form',
            'res_id': close.id,
        }
