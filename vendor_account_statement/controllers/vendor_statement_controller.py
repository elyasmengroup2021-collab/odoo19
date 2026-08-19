from odoo import http
from odoo.http import request


class VendorStatementController(http.Controller):

    @http.route(
        '/vendor_statement/view/<int:wizard_id>',
        type='http',
        auth='user',
        methods=['GET'],
        website=False,
    )
    def view_vendor_statement(self, wizard_id, **kwargs):
        wizard = request.env['vendor.statement.wizard'].sudo().browse(wizard_id)
        if not wizard.exists():
            return request.not_found()

        html_content, _ = request.env['ir.actions.report'].with_context(
            lang=wizard.partner_id.lang or 'en_US'
        )._render_qweb_html(
            'vendor_account_statement.report_vendor_partner_ledger',
            wizard.ids,
        )

        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
