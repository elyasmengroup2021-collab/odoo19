
from odoo import models, fields, api
class HrShift(models.Model):
    _name = 'hr.shift'
    _description = 'Shift'
    _order = 'sequence, shift_type'
    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(default=1)
    shift_type = fields.Selection([('morning','صباحي'),('afternoon','مسائي'),('night','ليلي'),('flexible','مرن'),('day_off','راحة')], required=True, default='morning')
    time_from = fields.Float(required=True, default=8.0)
    time_to = fields.Float(required=True, default=16.0)
    break_from = fields.Float()
    break_to = fields.Float()
    grace_in = fields.Integer(default=15)
    grace_out = fields.Integer(default=10)
    flexible_start = fields.Float()
    flexible_end = fields.Float()
    required_hours = fields.Float(default=8.0)
    work_hours = fields.Float(compute='_compute_work_hours', store=True)
    is_night_shift = fields.Boolean(compute='_compute_is_night', store=True)
    @api.depends('time_from','time_to','break_from','break_to')
    def _compute_work_hours(self):
        for rec in self:
            if rec.shift_type == 'flexible':
                rec.work_hours = rec.required_hours
            else:
                total = rec.time_to - rec.time_from
                if total < 0: total += 24
                if rec.break_from and rec.break_to:
                    b = rec.break_to - rec.break_from
                    if b > 0: total -= b
                rec.work_hours = total
    @api.depends('time_from','time_to')
    def _compute_is_night(self):
        for rec in self:
            rec.is_night_shift = rec.time_to < rec.time_from and rec.shift_type != 'flexible'
    @api.model
    def get_shift_for_employee_on_date(self, employee_id, date_obj):
        line = self.env['hr.shift.schedule.line'].search([('employee_id','=',employee_id),('date','=',date_obj)], limit=1)
        if line and line.shift_id:
            return line.shift_id
        emp = self.env['hr.employee'].browse(employee_id)
        if emp.shift_id:
            return emp.shift_id
        return self.search([('shift_type','=','morning')], limit=1)
