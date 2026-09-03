from odoo import api, SUPERUSER_ID


def _set_operational_day_offset(cr, registry):
    """Post-init hook to set operational_day_offset for night shift"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Find the night shift record
    night_shift = env['hr.shift'].search([('code', '=', 'NIG')], limit=1)
    
    if night_shift:
        # Set operational_day_offset to -1 for night shift
        night_shift.write({'operational_day_offset': -1})
