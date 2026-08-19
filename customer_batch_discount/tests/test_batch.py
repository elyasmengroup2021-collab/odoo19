from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase


class TestCustomerBatch(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Ahmed Farm'})
        cls.batch_model = cls.env['customer.batch']

    def test_create_batch_and_compute_end_date(self):
        batch = self.batch_model.create({
            'partner_id': self.partner.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        self.assertEqual(batch.name[:6], 'BATCH/')
        self.assertEqual(batch.end_date, date(2026, 2, 14))
        self.assertEqual(batch.state, 'draft')

    def test_child_contacts_cannot_open_parallel_batches(self):
        parent = self.env['res.partner'].create({'name': 'Parent Customer'})
        first_contact = self.env['res.partner'].create({
            'name': 'Parent Contact A',
            'parent_id': parent.id,
            'type': 'contact',
        })
        second_contact = self.env['res.partner'].create({
            'name': 'Parent Contact B',
            'parent_id': parent.id,
            'type': 'contact',
        })
        first = self.batch_model.create({
            'partner_id': first_contact.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        first.action_open()
        second = self.batch_model.create({
            'partner_id': second_contact.id,
            'start_date': date(2026, 3, 1),
            'duration_days': 45,
        })
        with self.assertRaises(ValidationError):
            second.action_open()
        first.action_close()
        second.action_open()
        self.assertEqual(second.state, 'open')

    def test_duration_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.batch_model.create({
                'partner_id': self.partner.id,
                'start_date': date(2026, 1, 1),
                'duration_days': 0,
            })

    def test_only_one_open_batch_per_customer(self):
        first = self.batch_model.create({
            'partner_id': self.partner.id,
            'start_date': date(2026, 1, 1),
            'duration_days': 45,
        })
        first.action_open()
        second = self.batch_model.create({
            'partner_id': self.partner.id,
            'start_date': date(2026, 3, 1),
            'duration_days': 45,
        })
        with self.assertRaises(Exception):
            second.action_open()
        first.action_close()
        second.action_open()
        self.assertEqual(second.state, 'open')
