# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError


class HrShiftAllowanceConfig(models.Model):
    _name = 'hr.shift.allowance.config'
    _description = 'Shift Allowance Department Configuration'
    _rec_name = 'department_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department', required=True, check_company=True)
    allowance_unit = fields.Selection([('shift', 'Shift'), ('hour', 'Hours')], string='Allowance Unit', required=True, default='shift')
    coefficient = fields.Float(string='Coefficient', required=True, default=1.0)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('department_company_unit_unique', 'unique(department_id, company_id, allowance_unit)', 'Only one shift allowance configuration is allowed per department/company/unit.'),
        ('coefficient_positive', 'CHECK(coefficient > 0)', 'Coefficient must be greater than zero.'),
    ]

    def init(self):
        tools.drop_constraint(self.env.cr, self._table, 'department_company_unique')

    @api.model
    def get_department_config(self, department, company, allowance_unit=False):
        domain = [
            ('department_id', '=', department.id),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ]
        if allowance_unit:
            domain.append(('allowance_unit', '=', allowance_unit))
        config = self.search(domain, order='allowance_unit desc, id desc', limit=1)
        if config:
            return config.allowance_unit, config.coefficient
        return allowance_unit or 'shift', 1.0

    @api.model
    def get_department_coefficients(self, department, company):
        configs = self.search([
            ('department_id', '=', department.id),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ])
        coefficients = {'shift': 1.0, 'hour': 1.0}
        for config in configs:
            coefficients[config.allowance_unit] = config.coefficient
        return coefficients


class HrShiftAllowanceClose(models.Model):
    _name = 'hr.shift.allowance.close'
    _description = 'Monthly Shift Allowance Closing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Reference', required=True, default='New', copy=False, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department', check_company=True)
    date_to = fields.Date(string='Closing Date', required=True)
    close_type = fields.Selection([
        ('pay', 'صرف وإغلاق الرصيد'),
        ('carry', 'ترحيل الرصيد للشهر التالي'),
    ], string='Closing Type', required=True)
    note = fields.Text(string='Notes')
    line_ids = fields.One2many('hr.shift.allowance.line', 'close_id', string='Closing Lines', readonly=True)
    total_quantity = fields.Float(string='Total Closed Balance', compute='_compute_total_quantity', store=True)
    export_file = fields.Binary(string='Excel File', readonly=True)
    export_filename = fields.Char(string='Excel Filename', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.shift.allowance.close') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.quantity')
    def _compute_total_quantity(self):
        for close in self:
            close.total_quantity = sum(close.line_ids.mapped('quantity'))

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('hr_compensation_days.action_report_shift_allowance_close').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Employee', 'Department', 'Date', 'Closed Balance', 'Previous Balance', 'Balance After', 'Notes'])
        for line in self.line_ids:
            writer.writerow([
                line.employee_id.name or '',
                line.department_id.name or '',
                line.date or '',
                line.quantity,
                line.balance_before,
                line.balance_after,
                line.note or '',
            ])
        self.write({
            'export_filename': '%s.xls' % self.name.replace('/', '_'),
            'export_file': base64.b64encode(buffer.getvalue().encode('utf-8-sig')),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/export_file/%s?download=true' % (self._name, self.id, self.export_filename),
            'target': 'self',
        }


class HrShiftAllowanceLine(models.Model):
    _name = 'hr.shift.allowance.line'
    _description = 'Employee Shift Allowance Balance Movement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Serial', required=True, default='New', copy=False, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True, check_company=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, readonly=True)
    date = fields.Date(string='Day', required=True, default=fields.Date.context_today, tracking=True)
    movement_type = fields.Selection([
        ('add', 'إضافة بدل وردية'),
        ('deduct', 'صرف بدل وردية'),
        ('close_paid', 'إغلاق رصيد مدفوع'),
    ], string='Form Type', required=True, default='add', tracking=True)
    allowance_unit = fields.Selection([('shift', 'Shift'), ('hour', 'Hours')], string='Allowance Unit', default='shift', required=True)
    input_quantity = fields.Float(string='Input Quantity', required=True, default=1.0, digits=(16, 2), tracking=True)
    coefficient = fields.Float(string='Coefficient', required=True, default=1.0, digits=(16, 4), tracking=True)
    quantity = fields.Float(string='Calculated Balance Quantity', required=True, default=1.0, digits=(16, 2), tracking=True)
    balance_before = fields.Float(string='Previous Balance', readonly=True, digits=(16, 2))
    balance_after = fields.Float(string='Balance', readonly=True, digits=(16, 2))
    close_id = fields.Many2one('hr.shift.allowance.close', string='Monthly Closing', readonly=True, ondelete='set null')
    note = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_shift_allowance_line_attachment_rel',
        'line_id',
        'attachment_id',
        string='Attachments',
        copy=False,
    )
    is_monthly_close = fields.Boolean(string='Monthly Closing', readonly=True)

    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'Shift allowance quantity must be greater than zero.'),
        ('input_quantity_positive', 'CHECK(input_quantity > 0)', 'Input quantity must be greater than zero.'),
        ('line_coefficient_positive', 'CHECK(coefficient > 0)', 'Coefficient must be greater than zero.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.shift.allowance.line') or 'New'
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            if employee and not vals.get('company_id'):
                vals['company_id'] = employee.company_id.id or self.env.company.id
            if not vals.get('quantity'):
                vals['quantity'] = vals.get('input_quantity', 0.0) * vals.get('coefficient', 1.0)
            balance_before = self.get_employee_balance(vals.get('employee_id'), vals.get('company_id'))
            vals['balance_before'] = balance_before
            vals['balance_after'] = balance_before + self._get_signed_quantity(vals.get('movement_type'), vals.get('quantity', 0.0))
        return super().create(vals_list)

    @api.constrains('employee_id', 'company_id')
    def _check_employee_company(self):
        for line in self:
            if line.employee_id.company_id and line.employee_id.company_id != line.company_id:
                raise ValidationError(_('The employee must belong to the selected company.'))

    @api.model
    def _get_signed_quantity(self, movement_type, quantity):
        if movement_type in ('deduct', 'close_paid'):
            return -quantity
        return quantity

    @api.model
    def get_employee_balance(self, employee_id, company_id=False, date_to=False):
        domain = [('employee_id', '=', employee_id)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        if date_to:
            domain.append(('date', '<=', date_to))
        lines = self.search(domain)
        balance = 0.0
        for line in lines:
            balance += self._get_signed_quantity(line.movement_type, line.quantity)
        return balance
