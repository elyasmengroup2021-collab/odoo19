from datetime import datetime, time, timedelta

from odoo import api, fields, models


class HrShift(models.Model):
    _name = 'hr.shift'
    _description = 'Shift'
    _order = 'sequence, shift_type, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(default=1)
    shift_type = fields.Selection([
        ('morning', 'Morning'), ('afternoon', 'Afternoon'), ('night', 'Night'),
        ('flexible', 'Flexible'), ('day_off', 'Day Off'),
    ], required=True, default='morning', translate=True)
    time_from = fields.Float(required=True, default=8.0)
    time_to = fields.Float(required=True, default=16.0)
    break_from = fields.Float()
    break_to = fields.Float()
    grace_in = fields.Integer(default=15)
    grace_out = fields.Integer(default=10)
    flexible_start = fields.Float()
    flexible_end = fields.Float()
    required_hours = fields.Float(default=8.0)
    operational_day_offset = fields.Integer(
        string='Operational Day Offset', default=0,
        help='Number of calendar days added to the operational date to build the shift start. Use -1 for a 00:00-08:00 shift belonging to the previous day.',
    )
    work_hours = fields.Float(compute='_compute_work_hours', store=True)
    is_night_shift = fields.Boolean(compute='_compute_is_night', store=True)

    @api.depends('time_from', 'time_to', 'break_from', 'break_to', 'required_hours', 'shift_type')
    def _compute_work_hours(self):
        for shift in self:
            if shift.shift_type == 'day_off':
                shift.work_hours = 0.0
                continue
            if shift.shift_type == 'flexible':
                shift.work_hours = shift.required_hours
                continue
            total = shift.time_to - shift.time_from
            if total < 0:
                total += 24
            if shift.break_from and shift.break_to and shift.break_to > shift.break_from:
                total -= shift.break_to - shift.break_from
            shift.work_hours = max(total, 0.0)

    @api.depends('time_from', 'time_to', 'shift_type')
    def _compute_is_night(self):
        for shift in self:
            shift.is_night_shift = (
                shift.shift_type not in ('flexible', 'day_off')
                and shift.time_to <= shift.time_from
            )

    @staticmethod
    def _float_time(value):
        hours = int(value or 0)
        minutes = round(((value or 0) - hours) * 60)
        if minutes == 60:
            hours += 1
            minutes = 0
        return time(hours % 24, minutes)

    def get_local_window(self, operational_date):
        self.ensure_one()
        start_date = operational_date + timedelta(days=self.operational_day_offset)
        start = datetime.combine(start_date, self._float_time(self.time_from))
        end_date = start_date + timedelta(days=1) if self.is_night_shift else start_date
        end = datetime.combine(end_date, self._float_time(self.time_to))
        return start, end

    def contains_local_datetime(self, local_dt, operational_date, tolerance_minutes=0):
        self.ensure_one()
        start, end = self.get_local_window(operational_date)
        tolerance = timedelta(minutes=tolerance_minutes)
        return start - tolerance <= local_dt <= end + tolerance

    @api.model
    def get_shift_for_employee_on_date(self, employee_id, date_obj):
        line = self.env['hr.shift.schedule.line'].search([
            ('employee_id', '=', employee_id), ('date', '=', date_obj),
        ], order='id desc', limit=1)
        if line and line.shift_id:
            return line.shift_id
        employee = self.env['hr.employee'].browse(employee_id)
        if employee.shift_id:
            return employee.shift_id
        return self.search([('shift_type', '=', 'morning'), ('active', '=', True)], limit=1)

    @api.model
    def get_shift_for_attendance(self, employee_id, check_in):
        if not check_in:
            return self.get_shift_for_employee_on_date(employee_id, fields.Date.context_today(self))
        local_dt = fields.Datetime.context_timestamp(self, check_in)
        for operational_date in (
            local_dt.date() - timedelta(days=1), local_dt.date(), local_dt.date() + timedelta(days=1)
        ):
            shift = self.get_shift_for_employee_on_date(employee_id, operational_date)
            if shift and shift.shift_type != 'day_off' and shift.contains_local_datetime(local_dt, operational_date):
                return shift
        return self.get_shift_for_employee_on_date(employee_id, local_dt.date())

    @api.model
    def get_operational_date_for_attendance(self, employee_id, check_in):
        if not check_in:
            return fields.Date.context_today(self)
        local_dt = fields.Datetime.context_timestamp(self, check_in)
        for operational_date in (local_dt.date() - timedelta(days=1), local_dt.date(), local_dt.date() + timedelta(days=1)):
            shift = self.get_shift_for_employee_on_date(employee_id, operational_date)
            if shift and shift.shift_type != 'day_off' and shift.contains_local_datetime(local_dt, operational_date):
                return operational_date
        return local_dt.date()
