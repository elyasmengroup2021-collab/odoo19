
from odoo import models, fields, api
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    shift_id = fields.Many2one('hr.shift', compute='_compute_shift_link', store=True)
    scheduled_shift_id = fields.Many2one('hr.shift', compute='_compute_shift_link', store=True)
    late_minutes = fields.Integer(compute='_compute_metrics', store=True)
    early_out_minutes = fields.Integer(compute='_compute_metrics', store=True)
    overtime_minutes = fields.Integer(compute='_compute_metrics', store=True)
    work_duration_hours = fields.Float(compute='_compute_metrics', store=True)
    status = fields.Selection([('present','حضور'),('late','تأخير'),('early','مبكر'),('absent','غياب'),('day_off','راحة'),('on_leave','إجازة')], compute='_compute_metrics', store=True)
    @api.depends('employee_id','check_in')
    def _compute_shift_link(self):
        for rec in self:
            if rec.employee_id and rec.check_in:
                d = rec.check_in.date()
                shift = self.env['hr.shift'].get_shift_for_employee_on_date(rec.employee_id.id, d)
                rec.shift_id = shift.id if shift else False
                rec.scheduled_shift_id = shift.id if shift else False
            else:
                rec.shift_id = False
                rec.scheduled_shift_id = False
    @api.depends('check_in','check_out','shift_id')
    def _compute_metrics(self):
        for rec in self:
            if not rec.check_in or not rec.shift_id:
                rec.late_minutes=0; rec.early_out_minutes=0; rec.overtime_minutes=0; rec.work_duration_hours=0; rec.status='present'
                continue
            shift=rec.shift_id
            if shift.shift_type=='flexible':
                if rec.check_in and rec.check_out:
                    diff=(rec.check_out-rec.check_in).total_seconds()/3600
                    rec.work_duration_hours=diff
                    if diff < shift.required_hours:
                        rec.late_minutes=int((shift.required_hours-diff)*60); rec.status='late'
                    else:
                        rec.overtime_minutes=int((diff-shift.required_hours)*60); rec.status='present'
                else:
                    rec.work_duration_hours=0; rec.late_minutes=0; rec.early_out_minutes=0; rec.overtime_minutes=0; rec.status='present'
                continue
            ci=rec.check_in; ci_float=ci.hour+ci.minute/60.0
            late=0
            if ci_float > shift.time_from + (shift.grace_in/60.0):
                late=int((ci_float-shift.time_from)*60)
            rec.late_minutes=late if late>0 else 0
            early=0; overtime=0; work_h=0
            if rec.check_out:
                co=rec.check_out; co_float=co.hour+co.minute/60.0
                if shift.is_night_shift and co_float < shift.time_from: co_float+=24
                expected_out=shift.time_to
                if shift.is_night_shift and expected_out < shift.time_from: expected_out+=24
                if co_float < expected_out - (shift.grace_out/60.0):
                    early=int((expected_out-co_float)*60)
                elif co_float > expected_out:
                    overtime=int((co_float-expected_out)*60)
                work_h=(rec.check_out-rec.check_in).total_seconds()/3600
            rec.early_out_minutes=early; rec.overtime_minutes=overtime; rec.work_duration_hours=work_h
            rec.status='late' if late>0 else 'early' if early>0 else 'present'
