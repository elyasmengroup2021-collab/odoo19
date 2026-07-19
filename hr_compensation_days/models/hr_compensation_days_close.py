# -*- coding: utf-8 -*-

from odoo import fields, models


class HrCompensationDaysClose(models.Model):
    _name = 'hr.compensation.days.close'
    _description = 'Shift Allowance Balance Closing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Branch', default=lambda self: self.env.company)
    employee_id = fields.Many2one('hr.employee', string='Employee')
    department_id = fields.Many2one('hr.department', string='Department')
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    action = fields.Selection(
        selection=[('pay', 'Close and Pay'), ('carry_forward', 'Carry Forward')],
        string='Action',
        required=True,
    )
    payment_date = fields.Date(string='Payment Date')
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('done', 'Done')],
        string='Status',
        default='done',
        required=True,
        readonly=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        'hr.compensation.days.close.line',
        'closing_id',
        string='Closing Lines',
    )
    move_ids = fields.One2many(
        'hr.compensation.days',
        'closing_id',
        string='Generated Entries',
        readonly=True,
    )

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_confirm(self):
        self.write({'state': 'done'})

    def action_print_pdf(self):
        return self.env.ref(
            'hr_compensation_days.action_report_close_shift_allowance_month'
        ).report_action(self)

    def action_print_xlsx(self):
        return self.env.ref(
            'hr_compensation_days.action_report_close_shift_allowance_month_xlsx'
        ).report_action(self)

    def unlink(self):
        generated_entries = self.mapped('move_ids')
        if generated_entries:
            generated_entries.write({'closing_id': False})
            generated_entries.unlink()
        return super().unlink()


class HrCompensationDaysCloseLine(models.Model):
    _name = 'hr.compensation.days.close.line'
    _description = 'Shift Allowance Balance Closing Line'
    _order = 'employee_id'

    closing_id = fields.Many2one(
        'hr.compensation.days.close',
        string='Balance Closing',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    department_id = fields.Many2one(related='employee_id.department_id', string='Department', store=True, readonly=True)
    company_id = fields.Many2one(related='closing_id.company_id', string='Branch', store=True, readonly=True)
    configured_allowance_unit = fields.Selection([('shift', 'Shift'), ('hour', 'Hours')], string='Configured Unit')
    allowance_coefficient = fields.Float(string='Days Coefficient', default=1.0)
    hours_allowance_coefficient = fields.Float(string='Hours Coefficient', default=1.0)
    balance_days = fields.Float(string='Balance Days')
    balance_hours = fields.Float(string='Balance Hours')
    balance_amount = fields.Float(string='Balance Amount')
    contract_id = fields.Many2one('hr.contract', string='Contract')
    rate = fields.Float(string='Daily Wage')
    hourly_rate = fields.Float(string='Hourly Wage')
    days_amount = fields.Float(string='Days Amount')
    hours_amount = fields.Float(string='Hours Amount')
    mission_amount = fields.Float(string='Mission Amount')
    amount = fields.Float(string='Total Amount')
    generated_entry_id = fields.Many2one(
        'hr.compensation.days',
        string='Generated Spend Entry',
        readonly=True,
    )

    def unlink(self):
        generated_entries = self.env['hr.compensation.days']
        for line in self:
            generated_entries |= line.closing_id.move_ids.filtered(lambda entry: entry.employee_id == line.employee_id)
        if generated_entries:
            generated_entries.write({'closing_id': False})
            generated_entries.unlink()
        return super().unlink()
