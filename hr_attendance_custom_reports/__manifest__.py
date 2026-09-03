{
    'name': 'Shift System Pro EN V18',
    'version': '19.0.18.0.0',
    'summary': 'Professional HR Reports English with Analytics and Leave Balance',
    'depends': ['hr', 'hr_attendance', 'hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'data/shift_data.xml',
        'views/hr_shift_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_employee_views.xml',
        'report/attendance_report.xml',
        'wizard/attendance_report_wizard_views.xml',
    ],
    'post_init_hook': '_set_operational_day_offset',
    'installable': True,
}
