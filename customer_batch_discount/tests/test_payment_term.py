from datetime import date

from odoo.tests.common import SavepointCase


class TestCustomerBatchPaymentTerm(SavepointCase):
    def test_batch_end_date_payment_term_line_returns_exact_batch_date(self):
        payment_term = self.env['account.payment.term'].create({
            'name': 'Batch End Date Test Term',
            'line_ids': [(0, 0, {
                'value': 'percent',
                'value_amount': 100.0,
                'delay_type': 'batch_end_date',
                'nb_days': 0,
            })],
        })
        line = payment_term.line_ids
        due_date = line.with_context(
            customer_batch_end_date=date(2026, 2, 14),
        )._get_due_date(date(2026, 1, 1))
        self.assertEqual(due_date, date(2026, 2, 14))

    def test_cancelled_batch_can_be_reset_to_draft_by_authorized_user(self):
        partner = self.env['res.partner'].create({'name': 'Reset Farm'})
        batch = self.env['customer.batch'].create({
            'partner_id': partner.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        batch.action_cancel()
        self.assertEqual(batch.state, 'cancelled')
        batch.action_reset_to_draft()
        self.assertEqual(batch.state, 'draft')
