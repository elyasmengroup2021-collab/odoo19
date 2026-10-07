/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DateTime } from "luxon";

export class AuditCutoffListController extends ListController {
    static template = "audit_cutoff_reports.AuditCutoffListView";
    static components = { ...ListController.components, Dropdown, DateTimePicker };

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        const ctx = this.props.context || {};
        this.cutoff = useState({
            date: ctx.cutoff_as_of_date || this.today(),
            reportType: ctx.cutoff_report_type,
            companyId: ctx.cutoff_company_id || false,
            last365: ctx.cutoff_last365 !== false,
        });
    }

    today() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }

    get cutoffDateTime() {
        return DateTime.fromISO(this.cutoff.date);
    }

    get cutoffButtonLabel() {
        return this.cutoffDateTime.toLocaleString(DateTime.DATE_SHORT);
    }

    async onCutoffDateSelect(value) {
        const date = Array.isArray(value) ? value[0] : value;
        if (!date) return;
        const iso = date.toISODate();
        if (iso === this.cutoff.date) return;
        this.cutoff.date = iso;
        try {
            const action = await this.orm.call("account.cutoff.report", "prepare_report_action", [
                this.cutoff.reportType,
                iso,
                this.cutoff.companyId || false,
                this.cutoff.last365,
            ]);
            await this.actionService.doAction(action, { clearBreadcrumbs: true });
        } catch (error) {
            this.notification.add(error.message || _t("Unable to change the cut-off date."), { type: "danger" });
        }
    }

    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        items.audit_export_excel = {
            isAvailable: () => true,
            sequence: 12,
            icon: "fa fa-file-excel-o",
            description: _t("Export Excel"),
            callback: () => this.exportAuditExcel(),
        };
        return items;
    }

    exportAuditExcel() {
        const domain = this.env.searchModel?.domain || this.props.domain || [];
        const groupBy = this.env.searchModel?.groupBy || [];
        const params = new URLSearchParams({
            session_key: this.props.context.cutoff_session || "",
            domain: JSON.stringify(domain),
            group_by: JSON.stringify(groupBy),
        });
        window.location.href = `/audit_cutoff_reports/export_xlsx_native?${params.toString()}`;
    }
}

registry.category("views").add("audit_cutoff_list", { ...listView, Controller: AuditCutoffListController });
