from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestReportTotals(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        journal = cls.company_data['default_journal_misc']
        cls.expense = cls.company_data['default_account_expense']
        cls.revenue = cls.company_data['default_account_revenue']
        cls.partner = cls.partner_a
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2025-01-15',
            'line_ids': [
                (0, 0, {'account_id': cls.expense.id, 'debit': 100, 'credit': 0}),
                (0, 0, {'account_id': cls.revenue.id, 'debit': 0, 'credit': 100}),
            ],
        })
        move.action_post()

    def test_general_ledger_has_total_last(self):
        report = self.env.ref('account_reports_community_v2.general_ledger_report')
        data = report.action_get_report_data({'date_from': '2025-01-01', 'date_to': '2025-01-31'})
        self.assertTrue(data['lines'])
        self.assertEqual(data['lines'][-1]['name'], 'Total')
        self.assertTrue(data['lines'][-1]['is_total'])

    def test_partner_ledger_has_total_last(self):
        report = self.env.ref('account_reports_community_v2.partner_ledger_report')
        data = report.action_get_report_data({'date_from': '2025-01-01', 'date_to': '2025-01-31'})
        self.assertTrue(data['lines'])
        self.assertEqual(data['lines'][-1]['name'], 'Total')
        self.assertTrue(data['lines'][-1]['is_total'])

    def test_trial_balance_accounts_summary_is_after_children(self):
        report = self.env.ref('account_reports_community_v2.trial_balance_report')
        data = report.action_get_report_data({'date_from': '2025-01-01', 'date_to': '2025-01-31'})
        accounts = data['lines'][0]
        self.assertTrue(accounts['children'])
        self.assertTrue(accounts['summary_at_bottom'])
