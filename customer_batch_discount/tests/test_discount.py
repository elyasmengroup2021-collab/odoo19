from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import SavepointCase


class TestCustomerBatchDiscount(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Discount Farm'})
        cls.product = cls.env['product.product'].create({
            'name': 'Discount Feed',
            'type': 'consu',
            'list_price': 100,
        })
        cls.batch = cls.env['customer.batch'].create({
            'partner_id': cls.partner.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        cls.batch.action_open()
        move = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'invoice_date': date(2026, 1, 10),
            'batch_id': cls.batch.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': cls.product.id,
                'quantity': 23,
                'price_unit': 100,
            })],
        })
        move.action_post()
        cls.batch.action_close()
        cls.batch.action_calculate_consumption()
        cls.company = cls.env.company
        cls.discount_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('account_type', 'not in', ('asset_receivable', 'liability_payable')),
            ('deprecated', '=', False),
        ], limit=1)
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        cls.company.write({
            'customer_batch_discount_account_id': cls.discount_account.id,
            'customer_batch_discount_journal_id': cls.journal.id,
        })

    def test_uniform_batch_rate_computes_amount_automatically(self):
        self.batch.discount_per_unit = 100.0
        line = self.batch.consumption_line_ids
        self.assertAlmostEqual(line.discount_amount, 2300.0)
        self.assertAlmostEqual(self.batch.total_discount, 2300.0)

    def test_direct_apply_uses_uniform_rate_and_label(self):
        self.batch.discount_label = 'April Customer Batch Rebate'
        self.batch.discount_per_unit = 100.0
        self.batch.action_apply_discount_from_lines()
        move = self.batch.discount_move_id
        self.assertEqual(self.batch.state, 'discount_applied')
        self.assertEqual(move.ref, 'April Customer Batch Rebate')
        self.assertEqual(self.batch.discount_move_ref, 'April Customer Batch Rebate')
        self.assertEqual(len(move.line_ids), 2)
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')), 2300.0)
        self.assertAlmostEqual(sum(move.line_ids.mapped('credit')), 2300.0)

    def test_apply_same_discount_creates_one_balanced_move(self):
        line = self.batch.consumption_line_ids
        move = self.batch.apply_discount({line.id: 100.0})
        self.assertEqual(self.batch.state, 'discount_applied')
        self.assertEqual(self.batch.discount_move_id, move)
        self.assertEqual(len(move.line_ids), 2)
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')), 2300.0)
        self.assertAlmostEqual(sum(move.line_ids.mapped('credit')), 2300.0)

    def test_duplicate_discount_is_rejected(self):
        line = self.batch.consumption_line_ids
        self.batch.apply_discount({line.id: 100.0})
        with self.assertRaises(UserError):
            self.batch.apply_discount({line.id: 100.0})
