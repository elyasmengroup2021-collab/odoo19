from datetime import timedelta

from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    shift_id = fields.Many2one('hr.shift', compute='_compute_shift_link', store=True, index=True)
    scheduled_shift_id = fields.Many2one('hr.shift', compute='_compute_shift_link', store=True, index=True)
    operational_date = fields.Date(compute='_compute_shift_link', store=True, index=True)
    late_minutes = fields.Integer(compute='_compute_metrics', store=True)
    early_out_minutes = fields.Integer(compute='_compute_metrics', store=True)
    overtime_minutes = fields.Integer(compute='_compute_metrics', store=True)
    work_duration_hours = fields.Float(compute='_compute_metrics', store=True)
    status = fields.Selection([
        ('present', 'Present'), ('late', 'Late'), ('early', 'Early'),
        ('absent', 'Absent'), ('day_off', 'Day Off'), ('on_leave', 'On Leave'),
    ], compute='_compute_metrics', store=True)

    @api.depends('employee_id', 'check_in')
    def _compute_shift_link(self):
        shift_model = self.env['hr.shift']
        for attendance in self:
            if attendance.employee_id and attendance.check_in:
                attendance.shift_id = shift_model.get_shift_for_attendance(
                    attendance.employee_id.id, attendance.check_in
                )
                attendance.scheduled_shift_id = attendance.shift_id
                attendance.operational_date = shift_model.get_operational_date_for_attendance(
                    attendance.employee_id.id, attendance.check_in
                )
            else:
                attendance.shift_id = False
                attendance.scheduled_shift_id = False
                attendance.operational_date = False

    @api.depends('check_in', 'check_out', 'shift_id', 'operational_date')
    def _compute_metrics(self):
        for attendance in self:
            attendance.late_minutes = 0
            attendance.early_out_minutes = 0
            attendance.overtime_minutes = 0
            attendance.work_duration_hours = 0.0
            attendance.status = 'present'
            if not attendance.check_in or not attendance.shift_id:
                continue

            shift = attendance.shift_id
            local_in = fields.Datetime.context_timestamp(self, attendance.check_in).replace(tzinfo=None)
            if attendance.check_out:
                local_out = fields.Datetime.context_timestamp(self, attendance.check_out).replace(tzinfo=None)
                attendance.work_duration_hours = max(
                    0.0, (local_out - local_in).total_seconds() / 3600
                )
            else:
                local_out = None

            if shift.shift_type == 'flexible':
                difference = attendance.work_duration_hours - shift.required_hours
                if difference < 0 and attendance.check_out:
                    attendance.late_minutes = round(abs(difference) * 60)
                    attendance.status = 'late'
                elif difference > 0:
                    attendance.overtime_minutes = round(difference * 60)
                continue

            operational_date = attendance.operational_date or local_in.date()
            start, end = shift.get_local_window(operational_date)
            late_boundary = start + timedelta(minutes=shift.grace_in)
            if local_in > late_boundary:
                attendance.late_minutes = round((local_in - start).total_seconds() / 60)

            if local_out:
                early_boundary = end - timedelta(minutes=shift.grace_out)
                if local_out < early_boundary:
                    attendance.early_out_minutes = round((end - local_out).total_seconds() / 60)
                elif local_out > end:
                    attendance.overtime_minutes = round((local_out - end).total_seconds() / 60)

            if attendance.late_minutes:
                attendance.status = 'late'
            elif attendance.early_out_minutes:
                attendance.status = 'early'
