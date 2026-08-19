from datetime import date

from odoo.tests.common import SavepointCase


class TestCustomerBatchConsumption(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Consumption Farm'})
        cls.product = cls.env['product.product'].create({
            'name': 'Feed Product',
            'type': 'consu',
            'list_price': 100,
        })
        cls.batch = cls.env['customer.batch'].create({
            'partner_id': cls.partner.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        cls.batch.action_open()

    def _create_invoice(self, quantity, move_type='out_invoice'):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': date(2026, 1, 10),
            'batch_id': self.batch.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': quantity,
                'price_unit': 100,
            })],
        })
        move.action_post()
        return move

    def test_credit_note_reduces_consumption(self):
        self._create_invoice(20)
        self._create_invoice(3, move_type='out_refund')
        self.batch.action_close()
        self.batch.action_calculate_consumption()
        line = self.batch.consumption_line_ids.filtered(
            lambda record: record.product_id == self.product
        )
        self.assertEqual(len(line), 1)
        self.assertEqual(line.quantity, 17)

    def test_invoice_from_another_customer_is_rejected(self):
        other_partner = self.env['res.partner'].create({'name': 'Other Farm'})
        with self.assertRaises(Exception):
            self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': other_partner.id,
                'invoice_date': date(2026, 1, 10),
                'batch_id': self.batch.id,
            })
