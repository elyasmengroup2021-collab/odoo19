from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class AccountCutoffReportLine(models.Model):
    _name = "account.cutoff.report.line"
    _description = "Audit Cut-off Report Line"
    _order = "partner_id, order_date, order_ref, id"
    _rec_name = "order_ref"

    session_key = fields.Char(index=True, required=True, readonly=True, copy=False)
    user_id = fields.Many2one("res.users", required=True, index=True, readonly=True, ondelete="cascade")
    report_type = fields.Selection([
        ("bills_to_receive", "Bills To Receive"),
        ("billed_not_received", "Billed Not Received"),
        ("invoices_to_issue", "Invoices To Be Issued"),
        ("invoiced_not_delivered", "Invoiced Not Delivered"),
    ], required=True, index=True, readonly=True)
    as_of_date = fields.Date(required=True, readonly=True, index=True)
    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)

    source_model = fields.Selection([
        ("purchase.order.line", "Purchase Order Line"),
        ("sale.order.line", "Sale Order Line"),
    ], required=True, readonly=True)
    source_line_id = fields.Integer(required=True, readonly=True, index=True)

    order_id = fields.Integer(readonly=True, index=True)
    order_ref = fields.Char(string="Order Reference", readonly=True, index=True)
    order_date = fields.Datetime(string="Order Date", readonly=True, index=True)
    confirmation_date = fields.Datetime(string="Confirmation Date", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner", readonly=True, index=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True, index=True)
    product_categ_id = fields.Many2one("product.category", string="Product Category", readonly=True, index=True)
    description = fields.Text(string="Description", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True, index=True)
    uom_id = fields.Many2one("uom.uom", string="Unit", readonly=True)
    company_currency_id = fields.Many2one("res.currency", string="Company Currency", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)

    product_type = fields.Selection([
        ("goods", "Goods"),
        ("service", "Service"),
    ], string="Product Type", readonly=True, index=True)
    within_last_365 = fields.Boolean(string="For the Last 365 Days", readonly=True, index=True)

    quantity = fields.Float(string="Quantity", readonly=True, aggregator="sum")
    received = fields.Float(string="Received", readonly=True, aggregator="sum")
    billed = fields.Float(string="Billed", readonly=True, aggregator="sum")
    delivered = fields.Float(string="Delivered", readonly=True, aggregator="sum")
    invoiced = fields.Float(string="Invoiced", readonly=True, aggregator="sum")
    unit_price = fields.Float(string="Unit Price", readonly=True, aggregator="avg")
    amount = fields.Monetary(string="Amount", currency_field="currency_id", readonly=True, aggregator="sum")

    _session_source_unique = models.Constraint(
        "UNIQUE(session_key, source_model, source_line_id)",
        "Duplicate cut-off line.",
    )

    @api.model
    def _check_report_access(self):
        if not self.env.user.has_group("account.group_account_user"):
            raise AccessError(_("You do not have access to accounting cut-off reports."))

    @api.model
    def create_snapshot(self, session_key, report_type, as_of_date, company_id, rows):
        self._check_report_access()
        self.sudo().search([("user_id", "=", self.env.user.id), ("session_key", "=", session_key)]).unlink()
        as_of_date = fields.Date.to_date(as_of_date)
        cutoff = as_of_date - relativedelta(days=365)
        vals_list = []
        source_model = "purchase.order.line" if report_type in ("bills_to_receive", "billed_not_received") else "sale.order.line"
        for row in rows:
            line = self.env[source_model].sudo().browse(row["id"]).exists()
            if not line:
                continue
            order = line.order_id
            product = line.product_id
            order_date = order.date_order
            if not order_date:
                continue
            order_day = fields.Datetime.to_datetime(order_date).date()
            ptype = product.type if product else False
            vals_list.append({
                "session_key": session_key,
                "user_id": self.env.user.id,
                "report_type": report_type,
                "as_of_date": as_of_date,
                "company_id": company_id,
                "source_model": source_model,
                "source_line_id": line.id,
                "order_id": order.id,
                "order_ref": order.name,
                "order_date": order_date,
                "confirmation_date": getattr(order, "date_approve", False),
                "partner_id": (line.partner_id if source_model == "purchase.order.line" else line.order_partner_id).id,
                "product_id": product.id,
                "product_categ_id": product.categ_id.id if product else False,
                "description": row.get("description") or line.name or "",
                "salesperson_id": order.user_id.id if source_model == "sale.order.line" and order.user_id else False,
                "uom_id": line.product_uom_id.id,
                "company_currency_id": line.company_id.currency_id.id,
                "currency_id": line.currency_id.id,
                "product_type": "service" if ptype == "service" else "goods",
                "within_last_365": cutoff <= order_day <= as_of_date,
                "quantity": row.get("quantity", 0.0),
                "received": row.get("received", 0.0),
                "billed": row.get("billed", 0.0),
                "delivered": row.get("delivered", 0.0),
                "invoiced": row.get("invoiced", 0.0),
                "unit_price": row.get("unit_price", 0.0),
                "amount": row.get("amount", 0.0),
            })
        if vals_list:
            self.sudo().create(vals_list)
        return len(vals_list)

    def action_create_accrual_entries(self):
        self._check_report_access()
        self = self.sudo()
        if not self:
            self = self.browse(self.env.context.get("active_ids", []))
        if not self:
            raise UserError(_("Select at least one line."))
        first = self[0]
        lines = self.search([
            ("session_key", "=", first.session_key),
            ("user_id", "=", self.env.user.id),
            ("id", "in", self.env.context.get("active_ids", self.ids)),
        ])
        if not lines:
            raise UserError(_("Select at least one line."))
        source_ids = lines.mapped("source_line_id")
        return self.env["account.cutoff.report"].action_create_accrual_wizard(
            first.report_type, source_ids, first.as_of_date, first.company_id.id
        )

    @api.model
    def cleanup_old_sessions(self):
        self.sudo().search([("create_date", "<", fields.Datetime.subtract(fields.Datetime.now(), days=2))]).unlink()
