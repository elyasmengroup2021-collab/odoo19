# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


OLD_MENU_XMLIDS = [
    'menu_hr_compensation_dashboard',
    'menu_hr_compensation_records',
    'menu_hr_compensation_requests',
    'menu_hr_compensation_reports',
    'menu_hr_compensation_report_pdf',
    'menu_hr_compensation_payroll_entries',
    'menu_hr_compensation_configuration',
    'menu_hr_compensation_config',
    'menu_hr_compensation_hr_settings',
]


def migrate(cr, version):
    """Hide menus left by the previous complex compensation implementation.

    The simplified module no longer defines those menus.  On upgraded databases,
    however, their ir.ui.menu records can still exist.  A migration is safer than
    loading fake menu records on fresh installs because it only touches XML IDs
    that already exist.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    group_no_one = env.ref('base.group_no_one', raise_if_not_found=False)
    group_commands = [(6, 0, [group_no_one.id])] if group_no_one else False
    for xmlid in OLD_MENU_XMLIDS:
        menu = env.ref('hr_compensation_days.%s' % xmlid, raise_if_not_found=False)
        if not menu:
            continue
        vals = {'active': False}
        if group_commands:
            vals['groups_id'] = group_commands
        menu.write(vals)
