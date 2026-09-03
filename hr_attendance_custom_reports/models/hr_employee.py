
from odoo import models, fields, api
class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    shift_id = fields.Many2one('hr.shift', string='الوردية الافتراضية')
    shift_type_pref = fields.Selection([('fixed','ثابت'),('rotational','تناوبي'),('flexible','مرن')], default='fixed')
    weekly_off_days = fields.Selection([('friday','الجمعة فقط'),('fri_sat','الجمعة والسبت'),('saturday','السبت فقط')], default='friday')
    current_shift_today = fields.Many2one('hr.shift', compute='_compute_today_shift')
    @api.depends()
    def _compute_today_shift(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.current_shift_today = self.env['hr.shift'].get_shift_for_employee_on_date(rec.id, today)
