from pathlib import Path

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReportFormatting(TransactionCase):

    def test_frontend_amount_formatter_uses_grouping(self):
        root = Path(__file__).parents[1]
        source = (root / 'static/src/account_reports/account_report_action.js').read_text()
        self.assertIn('Intl.NumberFormat', source)
        self.assertIn('useGrouping: true', source)
        self.assertNotIn('const formatted = value.toFixed(decimals);', source)
