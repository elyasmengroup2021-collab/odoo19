/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AuditCutoffBootstrap extends Component {
    static template = "audit_cutoff_reports.Bootstrap";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const ctx = this.props.action?.context || {};
        onWillStart(async () => {
            const action = await this.orm.call("account.cutoff.report", "prepare_report_action", [
                ctx.report_type || "bills_to_receive",
                ctx.as_of_date || false,
                ctx.company_id || false,
                ctx.last365 === undefined ? true : !!ctx.last365,
            ]);
            await this.action.doAction(action, { clearBreadcrumbs: true });
        });
    }
}

registry.category("actions").add("audit_cutoff_reports", AuditCutoffBootstrap);
