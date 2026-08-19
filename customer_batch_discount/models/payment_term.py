from odoo import fields, models


class AccountPaymentTermLine(models.Model):
    _inherit = 'account.payment.term.line'

    delay_type = fields.Selection(
        selection_add=[
            ('batch_end_date', 'Batch End Date'),
        ],
        ondelete={'batch_end_date': 'set default'},
    )

    def _get_due_date(self, date_ref):
        self.ensure_one()
        if self.delay_type == 'batch_end_date':
            batch_end_date = self.env.context.get('customer_batch_end_date')
            if batch_end_date:
                return fields.Date.to_date(batch_end_date)
        return super()._get_due_date(date_ref)
