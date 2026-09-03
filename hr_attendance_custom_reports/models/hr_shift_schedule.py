
from odoo import models, fields, api
from odoo.exceptions import ValidationError
class HrShiftSchedule(models.Model):
    _name = 'hr.shift.schedule'
    _description = 'Shift Schedule'
    _order = 'date_from desc'
    name = fields.Char(required=True, default='جدولة ورديات')
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    state = fields.Selection([('draft','مسودة'),('confirmed','مؤكدة')], default='draft')
    department_id = fields.Many2one('hr.department')
    line_ids = fields.One2many('hr.shift.schedule.line','schedule_id')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    @api.constrains('date_from','date_to')
    def _check_dates(self):
        for r in self:
            if r.date_from > r.date_to:
                raise ValidationError('من تاريخ يجب أن يكون قبل إلى تاريخ')
    def action_confirm(self):
        self.write({'state':'confirmed'})
    def action_draft(self):
        self.write({'state':'draft'})
class HrShiftScheduleLine(models.Model):
    _name = 'hr.shift.schedule.line'
    _description = 'Daily Shift Line'
    _order = 'date, employee_id'
    schedule_id = fields.Many2one('hr.shift.schedule', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True)
    date = fields.Date(required=True)
    shift_id = fields.Many2one('hr.shift', required=True)
    is_day_off = fields.Boolean(compute='_compute_day_off', store=True)
    notes = fields.Char()
    day_name = fields.Char(compute='_compute_day_name', store=True)
    @api.depends('date')
    def _compute_day_name(self):
        ar_days = ['الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']
        for rec in self:
            rec.day_name = ar_days[rec.date.weekday()] if rec.date else ''
    @api.depends('shift_id')
    def _compute_day_off(self):
        for rec in self:
            rec.is_day_off = rec.shift_id.shift_type == 'day_off' if rec.shift_id else False
    _sql_constraints = [('unique_emp_date','unique(employee_id, date)','لا يمكن تعيين ورديتين لنفس الموظف في نفس اليوم!')]
