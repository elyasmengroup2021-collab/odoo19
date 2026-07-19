# -*- coding: utf-8 -*-

from odoo import fields, models


class HrCompensationDaysMissionType(models.Model):
    _name = 'hr.compensation.days.mission.type'
    _description = 'Shift Allowance Mission Type'
    _order = 'sequence, name'

    name = fields.Char(string='Mission', required=True, translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    allowance_unit = fields.Selection(
        selection=[('day', 'Days'), ('hour', 'Hours'), ('amount', 'Amount')],
        string='Allowance Unit',
        required=True,
        default='day',
    )
    day_count = fields.Float(string='Default Days', required=True, default=1.0)
    hour_count = fields.Float(string='Default Hours', required=True, default=1.0)
    amount = fields.Float(string='Default Amount', required=True, default=1.0)
    active = fields.Boolean(default=True)
