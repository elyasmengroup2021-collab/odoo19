
from odoo import models, api
class ReportMovement(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.movement'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_movement_data()}
class ReportSinglePunch(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.single'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_single_punch_data()}
class ReportYearly(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.yearly'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_yearly_data()}
class ReportFingerprintList(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.fingerprint'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_fingerprint_list_data()}
class ReportDelay(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.delay'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_delay_data()}
class ReportAttendanceSheet(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.sheet'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_movement_data()}
class ReportAbsence(models.AbstractModel):
    _name = 'report.hr_attendance_custom_reports.absence'
    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['hr.attendance.report.wizard'].browse(docids)
        return {'docs':wizard,'data':wizard.get_absence_data()}
