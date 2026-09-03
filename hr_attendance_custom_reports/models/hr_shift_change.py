
from odoo import models, fields, api
class HrShiftChangeRequest(models.Model):
    _name = 'hr.shift.change.request'
    _description = 'Shift Change Request'
    _order = 'date desc'
    name = fields.Char(default='طلب تغيير وردية', readonly=True)
    employee_id = fields.Many2one('hr.employee', required=True, default=lambda self: self.env.user.employee_id)
    date = fields.Date(required=True)
    old_shift_id = fields.Many2one('hr.shift', compute='_compute_old', store=True, readonly=False)
    new_shift_id = fields.Many2one('hr.shift', required=True)
    reason = fields.Text()
    state = fields.Selection([('draft','مسودة'),('waiting','بانتظار'),('approved','تمت'),('refused','مرفوض')], default='draft')
    @api.depends('employee_id','date')
    def _compute_old(self):
        for rec in self:
            if rec.employee_id and rec.date:
                rec.old_shift_id = self.env['hr.shift'].get_shift_for_employee_on_date(rec.employee_id.id, rec.date)
            else:
                rec.old_shift_id = False
    def action_waiting(self):
        self.write({'state':'waiting'})
    def action_approve(self):
        for rec in self:
            line = self.env['hr.shift.schedule.line'].search([('employee_id','=',rec.employee_id.id),('date','=',rec.date)], limit=1)
            if line:
                line.shift_id = rec.new_shift_id.id
            else:
                sched = self.env['hr.shift.schedule'].search([('date_from','<=',rec.date),('date_to','>=',rec.date)], limit=1)
                if not sched:
                    sched = self.env['hr.shift.schedule'].create({'name': f'جدولة {rec.date}','date_from':rec.date,'date_to':rec.date,'state':'confirmed'})
                self.env['hr.shift.schedule.line'].create({'schedule_id':sched.id,'employee_id':rec.employee_id.id,'date':rec.date,'shift_id':rec.new_shift_id.id,'notes': f'تغيير من {rec.old_shift_id.name}'})
            rec.state = 'approved'
    def action_refuse(self):
        self.write({'state':'refused'})
