from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError
import io, base64
import xlsxwriter

class AttendanceReportWizard(models.TransientModel):
    _name = 'hr.attendance.report.wizard'
    _description = 'Attendance Report Wizard'
    report_type = fields.Selection([
        ('movement','Employee Movement'),
        ('single_punch','Single Punch'),
        ('yearly','Yearly Detailed'),
        ('fingerprint_list','Fingerprint List'),
        ('delay','Delay Report'),
        ('attendance_sheet','Attendance Sheet'),
        ('absence','Absence Report'),
        ('leave_balance','Leave Balance')], required=True, default='movement')
    date_from = fields.Date(string='Date From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.context_today)
    year = fields.Integer(string='Year', default=lambda self: datetime.now().year)
    department_id = fields.Many2one('hr.department', string='Department')
    shift_id = fields.Many2one('hr.shift', string='Shift')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    leave_type_id = fields.Many2one('hr.leave.type', string='Leave Type')
    html_preview = fields.Html(string='Preview', readonly=True)

    @api.onchange('department_id')
    def _onchange_department(self):
        if self.department_id:
            return {'domain': {'employee_ids': [('department_id', '=', self.department_id.id)]}}
        return {'domain': {'employee_ids': []}}

    @api.constrains('date_from','date_to')
    def _check_dates(self):
        for r in self:
            if r.date_from and r.date_to and r.date_from > r.date_to:
                raise ValidationError('Date From must be before Date To')

    def _get_employees(self):
        if self.employee_ids:
            return self.employee_ids
        if self.department_id:
            return self.env['hr.employee'].search([('department_id','=',self.department_id.id)])
        return self.env['hr.employee'].search([])

    def _float_to_hm(self,f):
        if f is None: return ''
        h=int(f)%24; m=int(round((f-int(f))*60))
        if m==60: h=(h+1)%24; m=0
        return f"{h:02d}:{m:02d}"

    def _get_shift_on_date(self, emp_id, d):
        try:
            return self.env['hr.shift'].get_shift_for_employee_on_date(emp_id, d)
        except:
            return False

    def get_movement_data(self):
        self.ensure_one()
        employees=self._get_employees()
        result=[]
        for emp in employees:
            days=[]
            cur=self.date_from
            while cur <= self.date_to:
                att=self.env['hr.attendance'].search([('employee_id','=',emp.id),('check_in','>=',datetime.combine(cur, datetime.min.time())),('check_in','<=',datetime.combine(cur, datetime.max.time()))], order='check_in')
                leave=self.env['hr.leave'].search([('employee_id','=',emp.id),('state','=','validate'),('date_from','<=',datetime.combine(cur, datetime.max.time())),('date_to','>=',datetime.combine(cur, datetime.min.time()))], limit=1)
                shift=self._get_shift_on_date(emp.id, cur)
                if self.shift_id and shift and shift.id != self.shift_id.id:
                    cur+=timedelta(days=1)
                    continue
                status='Present'
                ci_time=''
                co_time=''
                late=0
                work_h=0
                if not att and not leave:
                    status='Absent'
                elif leave:
                    status='On Leave'
                elif att:
                    a=att[0]
                    ci_time=a.check_in.strftime('%H:%M') if a.check_in else ''
                    co_time=a.check_out.strftime('%H:%M') if a.check_out else ''
                    late=a.late_minutes or 0
                    work_h=a.work_duration_hours or 0
                    if not a.check_out:
                        status='Incomplete'
                days.append({'date':cur.strftime('%Y-%m-%d'),'day_name':cur.strftime('%A'),'status':status,'shift_name':shift.name if shift else 'Morning','check_in':ci_time,'check_out':co_time,'late':late,'hours':round(work_h,2)})
                cur+=timedelta(days=1)
            result.append({'employee':emp,'days':days})
        return result

    def get_delay_data(self):
        self.ensure_one()
        employees=self._get_employees()
        lines=[]
        for emp in employees:
            cur=self.date_from
            while cur<=self.date_to:
                atts=self.env['hr.attendance'].search([('employee_id','=',emp.id),('check_in','>=',datetime.combine(cur, datetime.min.time())),('check_in','<=',datetime.combine(cur, datetime.max.time()))])
                for att in atts:
                    if att.late_minutes>0:
                        lines.append({'code':emp.barcode or emp.id,'name':emp.name,'date':cur.strftime('%Y-%m-%d'),'delay':att.late_minutes,'dept':emp.department_id.name if emp.department_id else ''})
                cur+=timedelta(days=1)
        return lines

    def get_absence_data(self):
        self.ensure_one()
        employees=self._get_employees()
        lines=[]
        cur=self.date_from
        while cur<=self.date_to:
            for emp in employees:
                att=self.env['hr.attendance'].search([('employee_id','=',emp.id),('check_in','>=',datetime.combine(cur, datetime.min.time())),('check_in','<=',datetime.combine(cur, datetime.max.time()))], limit=1)
                leave=self.env['hr.leave'].search([('employee_id','=',emp.id),('state','=','validate'),('date_from','<=',datetime.combine(cur, datetime.max.time())),('date_to','>=',datetime.combine(cur, datetime.min.time()))], limit=1)
                if not att and not leave:
                    lines.append({'date':cur.strftime('%Y-%m-%d'),'day':cur.strftime('%A'),'code':emp.barcode or emp.id,'name':emp.name,'dept':emp.department_id.name if emp.department_id else ''})
            cur+=timedelta(days=1)
        return lines

    def get_fingerprint_list_data(self):
        self.ensure_one()
        employees=self._get_employees()
        lines=[]
        for emp in employees:
            cur=self.date_from
            while cur<=self.date_to:
                atts=self.env['hr.attendance'].search([('employee_id','=',emp.id),('check_in','>=',datetime.combine(cur, datetime.min.time())),('check_in','<=',datetime.combine(cur, datetime.max.time()))], order='check_in')
                for att in atts:
                    if att.check_in:
                        lines.append({'date':cur.strftime('%Y-%m-%d'),'time':att.check_in.strftime('%H:%M'),'type':'IN','name':emp.name,'code':emp.barcode or emp.id,'dept':emp.department_id.name if emp.department_id else ''})
                    if att.check_out:
                        lines.append({'date':cur.strftime('%Y-%m-%d'),'time':att.check_out.strftime('%H:%M'),'type':'OUT','name':emp.name,'code':emp.barcode or emp.id,'dept':emp.department_id.name if emp.department_id else ''})
                cur+=timedelta(days=1)
        return lines

    def get_single_punch_data(self):
        self.ensure_one()
        employees=self._get_employees()
        lines=[]
        for emp in employees:
            cur=self.date_from
            while cur<=self.date_to:
                atts=self.env['hr.attendance'].search([('employee_id','=',emp.id),('check_in','>=',datetime.combine(cur, datetime.min.time())),('check_in','<=',datetime.combine(cur, datetime.max.time()))])
                for att in atts:
                    if not att.check_out:
                        lines.append({'date':cur.strftime('%Y-%m-%d'),'name':emp.name,'code':emp.barcode or emp.id,'time':att.check_in.strftime('%H:%M') if att.check_in else '','dept':emp.department_id.name if emp.department_id else ''})
                cur+=timedelta(days=1)
        return lines

    def get_attendance_sheet_data(self):
        return self.get_movement_data()

    def get_yearly_data(self):
        return self.get_movement_data()

    def get_leave_balance_data(self):
        self.ensure_one()
        employees=self._get_employees()
        result=[]
        leave_types = self.env['hr.leave.type'].search([('active', '=', True)]) if not self.leave_type_id else self.leave_type_id
        for emp in employees:
            for lt in leave_types:
                # Allocations
                allocations = self.env['hr.leave.allocation'].search([('employee_id','=',emp.id),('holiday_status_id','=',lt.id),('state','=','validate')])
                allocated = sum(allocations.mapped('number_of_days'))
                # Leaves taken
                leaves = self.env['hr.leave'].search([('employee_id','=',emp.id),('holiday_status_id','=',lt.id),('state','=','validate')])
                taken = sum(leaves.mapped('number_of_days'))
                remaining = allocated - taken
                if allocated > 0 or taken > 0:
                    result.append({'code':emp.barcode or emp.id,'name':emp.name,'dept':emp.department_id.name if emp.department_id else '','leave_type':lt.name,'allocated':round(allocated,2),'taken':round(taken,2),'remaining':round(remaining,2)})
        return result

    def _build_html(self):
        title = dict(self._fields['report_type'].selection).get(self.report_type)
        # Force white background for dark mode compatibility
        html = f"""
        <div style="font-family: Arial, sans-serif; padding:20px; background-color:#ffffff !important; color:#000000 !important; border-radius:8px;">
            <style>
                .report-table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
                .report-table th {{ background-color:#2c3e50 !important; color:#ffffff !important; padding:10px; text-align:left; font-weight:bold; }}
                .report-table td {{ padding:8px; border:1px solid #ddd; color:#000000 !important; background-color:#ffffff !important; }}
                .report-table tr:nth-child(even) td {{ background-color:#f8f9fa !important; }}
                .summary-box {{ background:#f1f8ff; border:2px solid #3498db; border-radius:8px; padding:15px; margin-top:20px; }}
                .summary-title {{ font-weight:bold; color:#2c3e50; font-size:16px; margin-bottom:10px; }}
            </style>
            <h2 style="color:#2c3e50 !important; border-bottom:3px solid #3498db; padding-bottom:10px;">{title}</h2>
            <p style="color:#000 !important;"><b>Period:</b> {self.date_from} to {self.date_to} | <b>Dept:</b> {self.department_id.name if self.department_id else 'All'} | <b>Employees:</b> {len(self._get_employees())}</p>
        """
        if self.report_type in ('movement','attendance_sheet','yearly'):
            data = self.get_movement_data()
            total_present=0
            total_absent=0
            total_leave=0
            total_hours=0
            for rec in data:
                html += f"<h3 style='background:#ecf0f1 !important; color:#2c3e50 !important; padding:10px; margin-top:20px; border-left:4px solid #3498db;'>{rec['employee'].name} ({rec['employee'].barcode or rec['employee'].id}) - {rec['employee'].department_id.name if rec['employee'].department_id else ''}</h3>"
                html += "<table class='report-table'><tr><th>Date</th><th>Day</th><th>Status</th><th>Check In</th><th>Check Out</th><th>Late</th><th>Hours</th></tr>"
                for d in rec['days']:
                    if d['status']=='Present': total_present+=1
                    elif d['status']=='Absent': total_absent+=1
                    elif d['status']=='On Leave': total_leave+=1
                    total_hours+=d['hours']
                    status_color = '#27ae60' if d['status']=='Present' else '#e74c3c' if d['status']=='Absent' else '#f39c12'
                    html += f"<tr><td>{d['date']}</td><td>{d['day_name']}</td><td style='color:{status_color} !important; font-weight:bold;'>{d['status']}</td><td>{d['check_in']}</td><td>{d['check_out']}</td><td>{d['late']}</td><td>{d['hours']}</td></tr>"
                html += "</table>"
            # Analytics
            html += f"<div class='summary-box'><div class='summary-title'>Report Analytics - {title}</div>"
            html += f"<p><b>Total Employees:</b> {len(data)} | <b>Total Days:</b> {(self.date_to - self.date_from).days + 1} | <b>Present:</b> {total_present} | <b>Absent:</b> {total_absent} | <b>On Leave:</b> {total_leave} | <b>Total Hours:</b> {round(total_hours,2)}</p>"
            if total_present+total_absent>0:
                rate = round(total_present/(total_present+total_absent)*100,1) if (total_present+total_absent)>0 else 0
                html += f"<p><b>Attendance Rate:</b> {rate}%</p>"
            html += "</div>"

        elif self.report_type == 'absence':
            lines = self.get_absence_data()
            html += "<table class='report-table'><tr><th>Date</th><th>Day</th><th>Code</th><th>Name</th><th>Department</th></tr>"
            for l in lines:
                html += f"<tr><td>{l['date']}</td><td>{l['day']}</td><td>{l['code']}</td><td>{l['name']}</td><td>{l['dept']}</td></tr>"
            html += "</table>"
            # Analytics
            distinct_emps = len(set([l['name'] for l in lines]))
            distinct_days = len(set([l['date'] for l in lines]))
            html += f"<div class='summary-box'><div class='summary-title'>Absence Analytics</div><p><b>Total Absence Records:</b> {len(lines)} | <b>Distinct Employees Absent:</b> {distinct_emps} | <b>Distinct Days with Absence:</b> {distinct_days} | <b>Total Employees in Filter:</b> {len(self._get_employees())}</p>"
            if len(self._get_employees())>0:
                html += f"<p><b>Absence Rate:</b> {round(len(lines)/((self.date_to - self.date_from).days+1)/len(self._get_employees())*100 if len(self._get_employees())>0 else 0,1)}% of total possible attendances</p>"
            html += "</div>"

        elif self.report_type == 'delay':
            lines = self.get_delay_data()
            html += "<table class='report-table'><tr><th>Date</th><th>Code</th><th>Name</th><th>Department</th><th>Delay (min)</th></tr>"
            total_delay=0
            for l in lines:
                total_delay+=l['delay']
                html += f"<tr><td>{l['date']}</td><td>{l['code']}</td><td>{l['name']}</td><td>{l['dept']}</td><td>{l['delay']}</td></tr>"
            html += "</table>"
            distinct = len(set([l['name'] for l in lines]))
            avg = round(total_delay/len(lines),1) if lines else 0
            html += f"<div class='summary-box'><div class='summary-title'>Delay Analytics</div><p><b>Total Delay Records:</b> {len(lines)} | <b>Total Delay Minutes:</b> {total_delay} | <b>Average Delay:</b> {avg} min | <b>Employees with Delays:</b> {distinct}</p></div>"

        elif self.report_type == 'fingerprint_list':
            lines = self.get_fingerprint_list_data()
            html += "<table class='report-table'><tr><th>Date</th><th>Time</th><th>Type</th><th>Code</th><th>Name</th><th>Department</th></tr>"
            for l in lines:
                html += f"<tr><td>{l['date']}</td><td>{l['time']}</td><td>{l['type']}</td><td>{l['code']}</td><td>{l['name']}</td><td>{l['dept']}</td></tr>"
            html += "</table>"
            ins = len([l for l in lines if l['type']=='IN'])
            outs = len([l for l in lines if l['type']=='OUT'])
            html += f"<div class='summary-box'><div class='summary-title'>Fingerprint Analytics</div><p><b>Total Punches:</b> {len(lines)} | <b>IN:</b> {ins} | <b>OUT:</b> {outs} | <b>Distinct Employees:</b> {len(set([l['name'] for l in lines]))}</p></div>"

        elif self.report_type == 'single_punch':
            lines = self.get_single_punch_data()
            html += "<table class='report-table'><tr><th>Date</th><th>Code</th><th>Name</th><th>Department</th><th>Time</th></tr>"
            for l in lines:
                html += f"<tr><td>{l['date']}</td><td>{l['code']}</td><td>{l['name']}</td><td>{l['dept']}</td><td>{l['time']}</td></tr>"
            html += "</table>"
            html += f"<div class='summary-box'><div class='summary-title'>Single Punch Analytics</div><p><b>Total Incomplete Records:</b> {len(lines)} | <b>Employees Affected:</b> {len(set([l['name'] for l in lines]))}</p></div>"

        elif self.report_type == 'leave_balance':
            lines = self.get_leave_balance_data()
            html += "<table class='report-table'><tr><th>Code</th><th>Name</th><th>Department</th><th>Leave Type</th><th>Allocated</th><th>Taken</th><th>Remaining</th></tr>"
            for l in lines:
                color = '#e74c3c' if l['remaining']<0 else '#27ae60'
                html += f"<tr><td>{l['code']}</td><td>{l['name']}</td><td>{l['dept']}</td><td>{l['leave_type']}</td><td>{l['allocated']}</td><td>{l['taken']}</td><td style='color:{color} !important; font-weight:bold;'>{l['remaining']}</td></tr>"
            html += "</table>"
            total_alloc = sum([l['allocated'] for l in lines])
            total_taken = sum([l['taken'] for l in lines])
            total_rem = sum([l['remaining'] for l in lines])
            html += f"<div class='summary-box'><div class='summary-title'>Leave Balance Analytics</div><p><b>Total Employees:</b> {len(set([l['name'] for l in lines]))} | <b>Total Allocated:</b> {total_alloc} days | <b>Total Taken:</b> {total_taken} days | <b>Total Remaining:</b> {total_rem} days</p><p><b>Utilization Rate:</b> {round(total_taken/total_alloc*100 if total_alloc>0 else 0,1)}%</p></div>"

        html += "</div>"
        return html

    def action_view_report(self):
        self.ensure_one()
        self.html_preview = self._build_html()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Report Viewer',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'view_id': self.env.ref('hr_attendance_custom_reports.view_attendance_report_viewer_form').id,
        }

    def action_export_excel(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Report')
        bold = workbook.add_format({'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white'})
        sheet.write(0,0,'Report', bold)
        sheet.write(0,1, dict(self._fields['report_type'].selection).get(self.report_type))
        sheet.write(1,0,'From', bold)
        sheet.write(1,1, str(self.date_from))
        sheet.write(2,0,'To', bold)
        sheet.write(2,1, str(self.date_to))
        sheet.write(3,0,'Department', bold)
        sheet.write(3,1, self.department_id.name if self.department_id else 'All')
        row=5
        if self.report_type in ('movement','attendance_sheet','yearly'):
            headers=['Employee','Code','Date','Day','Status','In','Out','Hours']
            for c,h in enumerate(headers): sheet.write(row,c,h,bold)
            row+=1
            for rec in self.get_movement_data():
                for d in rec['days']:
                    sheet.write(row,0,rec['employee'].name)
                    sheet.write(row,1,rec['employee'].barcode or rec['employee'].id)
                    sheet.write(row,2,d['date'])
                    sheet.write(row,3,d['day_name'])
                    sheet.write(row,4,d['status'])
                    sheet.write(row,5,d['check_in'])
                    sheet.write(row,6,d['check_out'])
                    sheet.write(row,7,d['hours'])
                    row+=1
            # summary
            row+=2
            sheet.write(row,0,'Analytics',bold)
        elif self.report_type == 'absence':
            headers=['Date','Day','Code','Name','Dept']
            for c,h in enumerate(headers): sheet.write(row,c,h,bold)
            row+=1
            for l in self.get_absence_data():
                sheet.write(row,0,l['date']); sheet.write(row,1,l['day']); sheet.write(row,2,l['code']); sheet.write(row,3,l['name']); sheet.write(row,4,l['dept']); row+=1
        elif self.report_type == 'delay':
            headers=['Date','Code','Name','Dept','Delay']
            for c,h in enumerate(headers): sheet.write(row,c,h,bold)
            row+=1
            for l in self.get_delay_data():
                sheet.write(row,0,l['date']); sheet.write(row,1,l['code']); sheet.write(row,2,l['name']); sheet.write(row,3,l['dept']); sheet.write(row,4,l['delay']); row+=1
        elif self.report_type == 'leave_balance':
            headers=['Code','Name','Dept','Leave Type','Allocated','Taken','Remaining']
            for c,h in enumerate(headers): sheet.write(row,c,h,bold)
            row+=1
            for l in self.get_leave_balance_data():
                sheet.write(row,0,l['code']); sheet.write(row,1,l['name']); sheet.write(row,2,l['dept']); sheet.write(row,3,l['leave_type']); sheet.write(row,4,l['allocated']); sheet.write(row,5,l['taken']); sheet.write(row,6,l['remaining']); row+=1
        else:
            headers=['Date','Time','Type','Code','Name']
            for c,h in enumerate(headers): sheet.write(row,c,h,bold)
            row+=1
            data = self.get_fingerprint_list_data() if self.report_type=='fingerprint_list' else self.get_single_punch_data()
            for l in data:
                sheet.write(row,0,l.get('date','')); sheet.write(row,1,l.get('time','')); sheet.write(row,2,l.get('type','')); sheet.write(row,3,l.get('code','')); sheet.write(row,4,l.get('name','')); row+=1
        workbook.close()
        output.seek(0)
        xls_data = base64.b64encode(output.read())
        filename = f"{self.report_type}_{self.date_from}_to_{self.date_to}.xlsx"
        att = self.env['ir.attachment'].create({'name':filename,'type':'binary','datas':xls_data,'store_fname':filename,'mimetype':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type':'ir.actions.act_url','url':f'/web/content/{att.id}?download=true','target':'self'}

    def action_print_pdf(self):
        self.ensure_one()
        mapping={'movement':'report_movement','single_punch':'report_single_punch','yearly':'report_yearly','fingerprint_list':'report_fingerprint_list','delay':'report_delay','attendance_sheet':'report_attendance_sheet','absence':'report_absence','leave_balance':'report_leave_balance'}
        report_id=mapping.get(self.report_type)
        if report_id:
            return self.env.ref(f"hr_attendance_custom_reports.{report_id}").report_action(self)
        return self.action_view_report()

