
from odoo import models, fields
from datetime import timedelta
class ShiftPlannerWizard(models.TransientModel):
    _name = 'hr.shift.planner.wizard'
    _description = 'Shift Planner'
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True)
    employee_ids = fields.Many2many('hr.employee', required=True)
    department_id = fields.Many2one('hr.department')
    pattern = fields.Selection([('fixed','وردية ثابتة'),('rotation_3','تناوب 3 ورديات'),('weekly_rotation','تناوب أسبوعي'),('flexible','مرن')], default='rotation_3', required=True)
    fixed_shift_id = fields.Many2one('hr.shift')
    rotation_shifts = fields.Many2many('hr.shift', domain=[('shift_type','!=','day_off')])
    include_weekend_off = fields.Boolean(default=True)
    schedule_id = fields.Many2one('hr.shift.schedule')
    def action_generate(self):
        self.ensure_one()
        schedule=self.schedule_id
        if not schedule:
            schedule=self.env['hr.shift.schedule'].create({'name': f'جدولة {self.date_from} إلى {self.date_to}','date_from':self.date_from,'date_to':self.date_to,'department_id':self.department_id.id if self.department_id else False,'state':'draft'})
        shifts=[]
        if self.pattern=='fixed': shifts=[self.fixed_shift_id] if self.fixed_shift_id else self.env['hr.shift'].search([('shift_type','=','morning')], limit=1)
        elif self.pattern in ('rotation_3','weekly_rotation'): shifts=self.rotation_shifts or self.env['hr.shift'].search([('shift_type','in',['morning','afternoon','night'])], order='sequence')
        elif self.pattern=='flexible': shifts=self.env['hr.shift'].search([('shift_type','=','flexible')], limit=1)
        if not shifts: shifts=self.env['hr.shift'].search([], limit=3)
        day_off_shift=self.env['hr.shift'].search([('shift_type','=','day_off')], limit=1)
        for emp in self.employee_ids:
            cur=self.date_from; idx=0
            while cur <= self.date_to:
                is_weekend=cur.weekday() in (4,5)
                if self.include_weekend_off and is_weekend and day_off_shift: shift_to_assign=day_off_shift
                else:
                    if self.pattern=='weekly_rotation':
                        week_num=(cur-self.date_from).days//7
                        shift_to_assign=shifts[week_num % len(shifts)] if shifts else shifts[0]
                    elif self.pattern=='rotation_3':
                        shift_to_assign=shifts[idx % len(shifts)] if shifts else shifts[0]; idx+=1
                    else: shift_to_assign=shifts[0] if shifts else self.env['hr.shift'].search([], limit=1)
                existing=self.env['hr.shift.schedule.line'].search([('employee_id','=',emp.id),('date','=',cur)], limit=1)
                if existing: existing.shift_id=shift_to_assign.id
                else: self.env['hr.shift.schedule.line'].create({'schedule_id':schedule.id,'employee_id':emp.id,'date':cur,'shift_id':shift_to_assign.id})
                cur+=timedelta(days=1)
        return {'type':'ir.actions.act_window','res_model':'hr.shift.schedule','res_id':schedule.id,'view_mode':'form','target':'current'}

