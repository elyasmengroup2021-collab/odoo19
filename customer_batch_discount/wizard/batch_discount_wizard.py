from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class CustomerBatchDiscountWizard(models.TransientModel):
    _name = 'customer.batch.discount.wizard'
    _description = 'Customer Batch Discount Wizard'

    batch_id = fields.Many2one(
        'customer.batch',
        string='Batch',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='batch_id.partner_id',
        string='Customer',
        readonly=True,
    )
    start_date = fields.Date(related='batch_id.start_date', readonly=True)
    end_date = fields.Date(related='batch_id.end_date', readonly=True)
    discount_per_ton = fields.Monetary(
        string='Discount / UoM',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='batch_id.currency_id',
        readonly=True,
    )
    line_ids = fields.One2many(
        'customer.batch.discount.wizard.line',
        'wizard_id',
        string='Consumption Lines',
    )
    total_discount = fields.Monetary(
        string='Total Discount',
        compute='_compute_total_discount',
        currency_field='currency_id',
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        batch = self.env['customer.batch'].browse(vals.get('batch_id'))
        if batch and 'line_ids' in fields_list:
            vals['line_ids'] = [
                Command.create({
                    'batch_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'discount_per_unit': line.discount_per_unit,
                })
                for line in batch.consumption_line_ids
            ]
        return vals

    @api.depends('line_ids.discount_amount')
    def _compute_total_discount(self):
        for wizard in self:
            wizard.total_discount = sum(wizard.line_ids.mapped('discount_amount'))

    def action_apply_to_all(self):
        for wizard in self:
            if wizard.discount_per_ton < 0:
                raise UserError(_('Discount values cannot be negative.'))
            wizard.line_ids.write({'discount_per_unit': wizard.discount_per_ton})
        return True

    def action_apply_discount(self):
        self.ensure_one()
        if self.batch_id.discount_move_id or self.batch_id.state == 'discount_applied':
            raise UserError(_('This batch discount has already been applied.'))
        values = {
            line.batch_line_id.id: line.discount_per_unit
            for line in self.line_ids
        }
        self.batch_id.apply_discount(values)
        return {'type': 'ir.actions.act_window_close'}


class CustomerBatchDiscountWizardLine(models.TransientModel):
    _name = 'customer.batch.discount.wizard.line'
    _description = 'Customer Batch Discount Wizard Line'

    wizard_id = fields.Many2one(
        'customer.batch.discount.wizard',
        required=True,
        ondelete='cascade',
    )
    batch_line_id = fields.Many2one(
        'customer.batch.line',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one('product.product', readonly=True)
    quantity = fields.Float(digits='Product Unit', readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    discount_per_unit = fields.Monetary(
        string='Discount / UoM',
        currency_field='currency_id',
    )
    discount_amount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_discount_amount',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='wizard_id.currency_id',
        readonly=True,
    )

    @api.depends('quantity', 'discount_per_unit')
    def _compute_discount_amount(self):
        for line in self:
            line.discount_amount = line.currency_id.round(
                line.quantity * line.discount_per_unit
            ) if line.currency_id else 0.0

    @api.constrains('discount_per_unit')
    def _check_discount(self):
        for line in self:
            if line.discount_per_unit < 0:
                raise UserError(_('Discount values cannot be negative.'))
