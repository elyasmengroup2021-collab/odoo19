import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { download } from "@web/core/network/download";

export class AccountReportAction extends Component {
    static template = "account_reports_community_v2.AccountReportAction";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    // -- lifecycle / data loading ---------------------------------------------

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.reportId = this.props.action.context.report_id;
        this.focusAccountId = this.props.action.context.focus_account_id || null;
        this.focusPartnerId = this.props.action.context.focus_partner_id || null;
        this.searchDebounceTimer = null;
        this.reportRequestSeq = 0;

        this.state = useState({
            report: null,
            unfoldedLineIds: [],
            openMenuLineId: null,
            dateFrom: this.props.action.context.date_from || null,
            dateTo: this.props.action.context.date_to || null,
            search: "",
            journalIds: [],
            allEntries: false,
            optionsMenuOpen: false,
            hierarchyAndSubtotals: false,
            includeAnalyticSimulations: false,
            unfoldAll: false,
            availableJournals: [],
            journalMenuOpen: false,
            currencyId: null,
            availableCurrencies: [],
            currencyMenuOpen: false,
            comparisonEnabled: false,
            comparisonMenuOpen: false,
            comparisonType: 'previous_period',
            comparisonCount: 1,
            comparisonDraftCount: 1,
            analyticGroupBy: null,
            analyticPickerType: 'analytic_account',
            analyticGroupQuery: '',
            analyticGroupValue: null,
            analyticAccountIds: [],
            analyticPlanIds: [],
            availableAnalyticAccounts: [],
            availableAnalyticPlans: [],
            analyticGroupMenuOpen: false,
            analyticSearchMoreOpen: false,
            analyticSearchMoreSelectedValue: null,
            analyticSearchMoreSelectedValues: [],
            analyticSearchRequestSeq: 0,
            periodGranularity: null,
            presetMenuOpen: false,
            partnerIds: [],
            availablePartners: [],
            partnerMenuOpen: false,
            partnerFilterQuery: "",
            isLoading: false,
            loadingMoreLineId: null,
            loadError: null,
        });

        this.display = { controlPanel: {} };

        this.closeMenusOnOutsideClick = (ev) => {
            if (!ev.target.closest(".o_account_reports_community_v2_toolbar")) {
                this.closeFilterMenus();
                this.state.openMenuLineId = null;
            }
        };
        onMounted(() => document.addEventListener("click", this.closeMenusOnOutsideClick));
        onWillUnmount(() => document.removeEventListener("click", this.closeMenusOnOutsideClick));
        onWillStart(async () => {
            await Promise.allSettled([
                this.loadReport(),
                this.loadJournalsSafe(),
                this.loadPartnersSafe(),
                this.loadCurrenciesSafe(),
                this.loadAnalyticValues(),
            ]);
        });
    }

    async loadJournals() {
        this.state.availableJournals = await this.orm.call(
            "account.report",
            "action_get_available_journals",
            [[this.reportId]],
        );
    }

    async loadJournalsSafe() {
        try {
            await this.loadJournals();
        } catch (_error) {
            this.state.availableJournals = [];
        }
    }

    async loadAnalyticValues() {
        // Older installed databases may still run the previous module code
        // until the module is upgraded. Do not let that transient RPC failure
        // crash the whole OWL report; the values become available after upgrade.
        try {
            this.state.availableAnalyticAccounts = await this.orm.call(
                "account.report", "action_get_available_analytic_accounts", [[this.reportId]],
                { limit: 10, offset: 0 },
            );
        } catch (_error) {
            this.state.availableAnalyticAccounts = [];
        }
        try {
            this.state.availableAnalyticPlans = await this.orm.call(
                "account.report", "action_get_available_analytic_plans", [[this.reportId]],
                { limit: 10, offset: 0 },
            );
        } catch (_error) {
            this.state.availableAnalyticPlans = [];
        }
    }
    async loadCurrencies() {
        this.state.availableCurrencies = await this.orm.call(
            "account.report",
            "action_get_available_currencies",
            [[this.reportId]],
        );
    }

    async loadCurrenciesSafe() {
        try {
            await this.loadCurrencies();
        } catch (_error) {
            this.state.availableCurrencies = [];
        }
    }

    async loadPartners() {
        this.state.availablePartners = await this.orm.call(
            "account.report",
            "action_get_available_partners",
            [[this.reportId]],
        );
    }

    async loadPartnersSafe() {
        try {
            await this.loadPartners();
        } catch (_error) {
            this.state.availablePartners = [];
        }
    }

    buildOptions() {
        return {
            date_from: this.state.dateFrom,
            date_to: this.state.dateTo,
            currency_id: this.state.currencyId,
            unfolded_line_ids: [...this.state.unfoldedLineIds],
            focus_account_id: this.focusAccountId,
            focus_partner_id: this.focusPartnerId,
            search: this.state.search,
            journal_ids: this.state.journalIds.length ? [...this.state.journalIds] : null,
            partner_ids: this.state.partnerIds.length ? [...this.state.partnerIds] : null,
            all_entries: this.state.allEntries,
            hierarchy_and_subtotals: this.state.hierarchyAndSubtotals,
            include_analytic_simulations: this.state.includeAnalyticSimulations,
            unfold_all: this.state.unfoldAll,
            collapse_all: Boolean(this.state.collapseAll),
            comparison_periods: this.state.comparisonEnabled ? this.state.comparisonCount : 0,
            comparison_type: this.state.comparisonType,
            analytic_group_by: this.state.analyticGroupBy,
            analytic_group_value: this.state.analyticGroupValue,
            analytic_account_ids: [...this.state.analyticAccountIds],
            analytic_plan_ids: [...this.state.analyticPlanIds],
            period_granularity: this.state.periodGranularity,
        };
    }

    toggleComparisonMenu() {
        this.closeFilterMenus('comparisonMenuOpen');
        this.state.comparisonMenuOpen = !this.state.comparisonMenuOpen;
    }
    selectComparisonType(type) {
        this.state.comparisonType = type;
        this.state.comparisonDraftCount = this.state.comparisonCount || 1;
    }
    onComparisonCountInput(ev) {
        const value = parseInt(ev.target.value, 10);
        this.state.comparisonDraftCount = Number.isFinite(value) ? Math.max(1, Math.min(value, 12)) : 1;
    }
    async applyComparison(type = this.state.comparisonType) {
        this.state.comparisonType = type;
        this.state.comparisonCount = Math.max(1, Math.min(parseInt(this.state.comparisonDraftCount, 10) || 1, 12));
        this.state.comparisonEnabled = true;
        this.state.comparisonMenuOpen = false;
        await this.loadReport();
    }
    async clearComparison() {
        this.state.comparisonEnabled = false;
        this.state.comparisonMenuOpen = false;
        await this.loadReport();
    }

    async loadReport() {
        const requestSeq = ++this.reportRequestSeq;
        this.state.isLoading = true;
        this.state.loadError = null;
        try {
            const report = await this.orm.call(
                "account.report",
                "action_get_report_data",
                [[this.reportId]],
                { options: this.buildOptions() },
            );
            // A fast sequence of searches/filter changes can return out of order.
            // Never allow an older financial response to replace a newer one.
            if (requestSeq !== this.reportRequestSeq) {
                return;
            }
            this.state.report = report;
            if (!this.state.dateFrom) {
                this.state.dateFrom = this.state.report.options.date_from;
            }
            if (!this.state.dateTo) {
                this.state.dateTo = this.state.report.options.date_to;
            }
            if (!this.state.currencyId) {
                this.state.currencyId = this.state.report.options.currency_id;
            }
            if (!this.state.periodGranularity && this.state.report.options.period_granularity) {
                this.state.periodGranularity = this.state.report.options.period_granularity;
            }
            this.markFetched(this.state.report.lines || []);
        } catch (error) {
            if (requestSeq === this.reportRequestSeq) {
                this.state.loadError = error?.message || "Unable to load the report.";
            }
        } finally {
            if (requestSeq === this.reportRequestSeq) {
                this.state.isLoading = false;
            }
        }
    }

    /** PDF/XLSX export both hit a plain HTTP controller (not orm.call) since
     * the response is a binary file, not JSON - the controller re-resolves
     * options itself server-side (with export_mode forced on) rather than
     * trusting whatever the browser currently has rendered, so the export
     * always reflects the full data set regardless of what's folded/paged
     * in the UI right now. */
    async exportXlsx() {
        await download({
            url: "/account_reports_community_v2/xlsx",
            data: {
                report_id: this.reportId,
                options: JSON.stringify(this.buildOptions()),
            },
        });
    }

    async exportPdf() {
        await download({
            url: "/account_reports_community_v2/pdf",
            data: {
                report_id: this.reportId,
                options: JSON.stringify(this.buildOptions()),
            },
        });
    }

    markFetched(lines) {
        for (const line of lines) {
            if (line.unfolded) {
                line._fetched = true;
            }
            if (line.children && line.children.length) {
                this.markFetched(line.children);
            }
        }
    }

    /** Formats a monetary value using the browser/Odoo user locale.  The
     * previous implementation used Number.toFixed(), which deliberately
     * omits thousands separators (1000.00 instead of 1,000.00). */
    formatDateValue(value) {
        if (!value) return "";
        const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!match) return String(value);
        const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
        const locale = document.documentElement.lang || navigator.language || "en-US";
        return new Intl.DateTimeFormat(locale, {day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC"}).format(date);
    }
    formatAmount(value) {
        if (value === null || value === undefined) {
            return "";
        }
        const currency = (this.state.report && this.state.report.currency) || {};
        const decimals = currency.decimal_places != null ? currency.decimal_places : 2;
        const locale = document.documentElement.lang || navigator.language || "en-US";
        const formatted = new Intl.NumberFormat(locale, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
            useGrouping: true,
        }).format(value);
        if (!currency.symbol) {
            return formatted;
        }
        return currency.position === "before" ? `${currency.symbol}${formatted}` : `${formatted} ${currency.symbol}`;
    }

    // -- filters shared across every report type (date range/presets, search,
    // journal, posted-vs-all, comparison toggle, partner filter dropdown) ---

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        // A manual edit may no longer be aligned to a calendar month/quarter/
        // year boundary, so comparison falls back to a plain day-count shift.
        this.state.periodGranularity = null;
        await this.loadReport();
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        this.state.periodGranularity = null;
        await this.loadReport();
    }
    async applyCustomDateRange() {
        this.state.periodGranularity = null;
        this.state.presetMenuOpen = false;
        await this.loadReport();
    }

    closeFilterMenus(exceptName = null) {
        for (const name of ["presetMenuOpen", "journalMenuOpen", "currencyMenuOpen", "optionsMenuOpen", "partnerMenuOpen", "comparisonMenuOpen", "analyticGroupMenuOpen"]) {
            if (name !== exceptName && name in this.state) this.state[name] = false;
        }
    }
    togglePresetMenu() {
        this.closeFilterMenus("presetMenuOpen");
        this.state.presetMenuOpen = !this.state.presetMenuOpen;
    }

    static formatDate(d) {
        const pad = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    async applyDatePreset(preset) {
        const serverToday = this.state.report?.options?.today;
        const today = serverToday ? new Date(`${serverToday}T00:00:00`) : new Date();
        const y = today.getFullYear();
        const m = today.getMonth(); // 0-indexed
        let from;
        let to;
        let granularity;

        if (preset === "today") {
            from = today;
            to = today;
            granularity = null;
        } else if (preset === "this_month") {
            from = new Date(y, m, 1);
            to = new Date(y, m + 1, 0);
            granularity = "month";
        } else if (preset === "last_month") {
            from = new Date(y, m - 1, 1);
            to = new Date(y, m, 0);
            granularity = "month";
        } else if (preset === "this_quarter") {
            const qStart = Math.floor(m / 3) * 3;
            from = new Date(y, qStart, 1);
            to = new Date(y, qStart + 3, 0);
            granularity = "quarter";
        } else if (preset === "last_quarter") {
            const qStart = Math.floor(m / 3) * 3 - 3;
            from = new Date(y, qStart, 1);
            to = new Date(y, qStart + 3, 0);
            granularity = "quarter";
        } else if (preset === "this_year") {
            const fiscalFrom = this.state.report?.options?.fiscalyear_from;
            const fiscalTo = this.state.report?.options?.fiscalyear_to;
            from = fiscalFrom ? new Date(`${fiscalFrom}T00:00:00`) : new Date(y, 0, 1);
            to = fiscalTo ? new Date(`${fiscalTo}T00:00:00`) : new Date(y, 11, 31);
            granularity = "year";
        } else if (preset === "last_year") {
            const fiscalFrom = this.state.report?.options?.fiscalyear_from;
            const fiscalTo = this.state.report?.options?.fiscalyear_to;
            from = fiscalFrom ? new Date(`${fiscalFrom}T00:00:00`) : new Date(y - 1, 0, 1);
            to = fiscalTo ? new Date(`${fiscalTo}T00:00:00`) : new Date(y - 1, 11, 31);
            from.setFullYear(from.getFullYear() - 1);
            to.setFullYear(to.getFullYear() - 1);
            granularity = "year";
        } else {
            return;
        }

        this.state.dateFrom = AccountReportAction.formatDate(from);
        this.state.dateTo = AccountReportAction.formatDate(to);
        this.state.periodGranularity = granularity;
        this.state.presetMenuOpen = false;
        await this.loadReport();
    }

    get isPartnerBasedReport() {
        const handler = this.state.report && this.state.report.report_handler;
        return handler === 'partner_ledger' || handler === 'aged_partner_balance';
    }

    get searchPlaceholder() {
        const handler = this.state.report && this.state.report.report_handler;
        if (this.isPartnerBasedReport) {
            return "Search partners...";
        }
        if (handler === "tax_report") {
            return "Search taxes...";
        }
        if (handler === "journal_report") {
            return "Search journals...";
        }
        return "Search accounts...";
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        clearTimeout(this.searchDebounceTimer);
        this.searchDebounceTimer = setTimeout(() => this.loadReport(), 400);
    }

    toggleJournalMenu() {
        this.closeFilterMenus("journalMenuOpen");
        this.state.journalMenuOpen = !this.state.journalMenuOpen;
    }

    async toggleJournal(journalId) {
        const index = this.state.journalIds.indexOf(journalId);
        if (index === -1) {
            this.state.journalIds.push(journalId);
        } else {
            this.state.journalIds.splice(index, 1);
        }
        await this.loadReport();
    }

    get journalFilterLabel() {
        if (!this.state.journalIds.length) {
            return "All Journals";
        }
        if (this.state.journalIds.length === 1) {
            const journal = this.state.availableJournals.find((j) => j.id === this.state.journalIds[0]);
            return journal ? journal.name : "1 Journal";
        }
        return `${this.state.journalIds.length} Journals`;
    }

    toggleCurrencyMenu() {
        this.closeFilterMenus("currencyMenuOpen");
        this.state.currencyMenuOpen = !this.state.currencyMenuOpen;
    }

    toggleOptionsMenu() {
        this.closeFilterMenus("optionsMenuOpen");
        this.state.optionsMenuOpen = !this.state.optionsMenuOpen;
    }
    toggleAnalyticGroupMenu() {
        this.closeFilterMenus("analyticGroupMenuOpen");
        if (!this.state.analyticPickerType) {
            this.state.analyticPickerType = 'analytic_account';
            this.state.analyticGroupQuery = '';
        }
        this.loadAnalyticSearchResults(10);
        this.state.analyticGroupMenuOpen = !this.state.analyticGroupMenuOpen;
    }
    async selectAnalyticGroupBy(value) {
        this.state.analyticGroupBy = value || null;
        this.state.analyticGroupValue = null;
        this.state.analyticGroupQuery = '';
        this.state.analyticGroupMenuOpen = false;
        if (value) {
            await this.loadAnalyticSearchResults();
        }
        await this.loadReport();
    }
    selectAnalyticGroupType(value) {
        this.state.analyticPickerType = value;
        this.state.analyticGroupValue = null;
        this.state.analyticGroupQuery = '';
        this.loadAnalyticSearchResults(10);
    }
    onAnalyticGroupQueryInput(ev) {
        this.state.analyticGroupQuery = ev.target.value || '';
        clearTimeout(this.analyticSearchTimer);
        this.analyticSearchTimer = setTimeout(() => this.loadAnalyticSearchResults(10), 250);
    }
    async loadAnalyticSearchResults(limit = 10) {
        if (!this.state.analyticPickerType) return;
        const requestSeq = ++this.state.analyticSearchRequestSeq;
        try {
            const values = await this.orm.call(
                'account.report', 'action_search_analytic_values',
                [[this.reportId]],
                { kind: this.state.analyticPickerType, query: this.state.analyticGroupQuery || '', limit, offset: 0 },
            );
            if (requestSeq !== this.state.analyticSearchRequestSeq) return;
            if (this.state.analyticPickerType === 'analytic_account') {
                this.state.availableAnalyticAccounts = values || [];
            } else {
                this.state.availableAnalyticPlans = values || [];
            }
        } catch (_error) {
            // Local filtering remains available if the optional RPC is unavailable.
        }
    }
    get filteredAnalyticAccounts() {
        const q = (this.state.analyticGroupQuery || '').toLowerCase().trim();
        return !q ? this.state.availableAnalyticAccounts : this.state.availableAnalyticAccounts.filter((item) => `${item.name} ${item.plan_name || ''}`.toLowerCase().includes(q));
    }
    get filteredAnalyticPlans() {
        const q = (this.state.analyticGroupQuery || '').toLowerCase().trim();
        return !q ? this.state.availableAnalyticPlans : this.state.availableAnalyticPlans.filter((item) => item.name.toLowerCase().includes(q));
    }
    async selectAnalyticGroupValue(value) {
        const id = Number(value) || null;
        if (!id) return;
        const target = this.state.analyticPickerType === 'analytic_plan' ? this.state.analyticPlanIds : this.state.analyticAccountIds;
        const index = target.indexOf(id);
        if (index === -1) target.push(id);
        else target.splice(index, 1);
        this.state.analyticGroupBy = this.state.analyticPickerType;
        this.state.analyticGroupValue = id;
        await this.loadReport();
    }

    removeAnalyticValue(kind, value) {
        const target = kind === 'analytic_plan' ? this.state.analyticPlanIds : this.state.analyticAccountIds;
        const index = target.indexOf(Number(value));
        if (index !== -1) target.splice(index, 1);
        if (!this.state.analyticAccountIds.length && !this.state.analyticPlanIds.length) {
            this.state.analyticGroupBy = null;
            this.state.analyticGroupValue = null;
        }
        this.loadReport();
    }

    get selectedAnalyticAccounts() {
        return this.state.availableAnalyticAccounts.filter((item) => this.state.analyticAccountIds.includes(item.id));
    }

    get selectedAnalyticPlans() {
        return this.state.availableAnalyticPlans.filter((item) => this.state.analyticPlanIds.includes(item.id));
    }
    clearAnalyticValues() {
        this.state.analyticAccountIds.splice(0);
        this.state.analyticPlanIds.splice(0);
        this.state.analyticGroupBy = null;
        this.state.analyticGroupValue = null;
        this.loadReport();
    }
    openAnalyticSearchMore() {
        this.state.analyticGroupMenuOpen = false;
        const target = this.state.analyticPickerType === 'analytic_plan' ? this.state.analyticPlanIds : this.state.analyticAccountIds;
        this.state.analyticSearchMoreSelectedValues = [...target];
        this.state.analyticSearchMoreSelectedValue = target.length ? target[target.length - 1] : null;
        this.state.analyticSearchMoreOpen = true;
        this.loadAnalyticSearchResults(200);
    }
    closeAnalyticSearchMore() {
        this.state.analyticSearchMoreOpen = false;
        this.state.analyticSearchMoreSelectedValue = null;
        this.state.analyticSearchMoreSelectedValues = [];
    }
    selectAnalyticSearchMoreValue(value) {
        const id = Number(value) || null;
        if (!id) return;
        const values = this.state.analyticSearchMoreSelectedValues;
        const index = values.indexOf(id);
        if (index === -1) values.push(id);
        else values.splice(index, 1);
        this.state.analyticSearchMoreSelectedValue = id;
    }
    async applyAnalyticSearchMore() {
        const selected = this.state.analyticSearchMoreSelectedValues;
        if (selected.length) {
            const target = this.state.analyticPickerType === 'analytic_plan' ? this.state.analyticPlanIds : this.state.analyticAccountIds;
            for (const id of selected) {
                if (!target.includes(id)) target.push(id);
            }
            this.state.analyticGroupBy = this.state.analyticPickerType;
            this.state.analyticGroupValue = selected[selected.length - 1];
        }
        this.state.analyticSearchMoreOpen = false;
        this.state.analyticSearchMoreSelectedValue = null;
        this.state.analyticSearchMoreSelectedValues = [];
        await this.loadReport();
    }
    get periodFilterLabel() {
        if (!this.state.dateFrom || !this.state.dateTo) return 'Period';
        const from = new Date(`${this.state.dateFrom}T00:00:00`);
        const to = new Date(`${this.state.dateTo}T00:00:00`);
        const year = to.getFullYear();
        if (this.state.periodGranularity === 'year') return String(year);
        if (this.state.periodGranularity === 'quarter') return `Q${Math.floor(to.getMonth() / 3) + 1} ${year}`;
        if (this.state.periodGranularity === 'month') return to.toLocaleDateString(undefined, {month: 'short', year: 'numeric'});
        return 'Period';
    }
    get analyticGroupLabel() {
        // Enterprise keeps the toolbar button name stable; the selected
        // account/plan is shown inside the opened two-level picker.
        return 'Analytic Group By';
    }

    async toggleDraftEntries() {
        this.state.allEntries = !this.state.allEntries;
        await this.loadReport();
    }

    async toggleHierarchyAndSubtotals() {
        this.state.hierarchyAndSubtotals = !this.state.hierarchyAndSubtotals;
        await this.loadReport();
    }

    async toggleAnalyticSimulations() {
        this.state.includeAnalyticSimulations = !this.state.includeAnalyticSimulations;
        await this.loadReport();
    }

    async toggleUnfoldAll() {
        const enabled = !this.state.unfoldAll;
        this.state.unfoldAll = enabled;
        this.state.unfoldedLineIds = [];
        this.state.collapseAll = !enabled;
        await this.loadReport();
        // collapse_all is a transition command, not a persistent filter.
        this.state.collapseAll = false;
    }

    get comparisonLabel() {
        if (!this.state.comparisonEnabled) return 'Comparison';
        const name = this.state.comparisonType === 'same_period_last_year' ? 'Same Period Last Year' : 'Previous Period';
        return `Comparison: ${name} (${this.state.comparisonCount})`;
    }

    get optionsLabel() {
        return this.state.allEntries ? "Options: Include Draft Entries" : "Options: Posted Entries Only";
    }

    async selectCurrency(currencyId) {
        this.state.currencyId = currencyId;
        this.state.currencyMenuOpen = false;
        await this.loadReport();
    }

    /** Unlike the Journal filter (multi-select, "All Journals" when
     * empty), exactly one currency is always active - this label shows
     * that currency's name, resolved server-side to a sensible default
     * (the single selected company's currency, or the active company's
     * when several are selected) until the user picks one explicitly. */
    get currencyFilterLabel() {
        const currency = this.state.availableCurrencies.find((c) => c.id === this.state.currencyId);
        return currency ? currency.name : "Currency";
    }

    async toggleAllEntries() {
        await this.toggleDraftEntries();
    }

    togglePartnerMenu() {
        this.closeFilterMenus("partnerMenuOpen");
        this.state.partnerMenuOpen = !this.state.partnerMenuOpen;
    }

    async togglePartnerFilter(partnerId) {
        const index = this.state.partnerIds.indexOf(partnerId);
        if (index === -1) {
            this.state.partnerIds.push(partnerId);
        } else {
            this.state.partnerIds.splice(index, 1);
        }
        await this.loadReport();
    }

    onPartnerFilterQueryInput(ev) {
        this.state.partnerFilterQuery = ev.target.value;
    }

    get filteredAvailablePartners() {
        const query = this.state.partnerFilterQuery.toLowerCase();
        if (!query) {
            return this.state.availablePartners;
        }
        return this.state.availablePartners.filter((p) => p.name.toLowerCase().includes(query));
    }

    get partnerFilterLabel() {
        if (!this.state.partnerIds.length) {
            return "All Partners";
        }
        if (this.state.partnerIds.length === 1) {
            const partner = this.state.availablePartners.find((p) => p.id === this.state.partnerIds[0]);
            return partner ? partner.name : "1 Partner";
        }
        return `${this.state.partnerIds.length} Partners`;
    }

    // -- generic report (Trial Balance / Balance Sheet / P&L) ------------
    // rendered by the account_reports_community_v2.ReportLines template.

    async toggleLine(line) {
        if (!line.foldable) {
            return;
        }
        if (line.unfolded) {
            // Folding never needs new data - just hide what's already rendered.
            line.unfolded = false;
            const index = this.state.unfoldedLineIds.indexOf(line.real_line_id);
            if (index !== -1) {
                this.state.unfoldedLineIds.splice(index, 1);
            }
            return;
        }
        line.unfolded = true;
        if (!this.state.unfoldedLineIds.includes(line.real_line_id)) {
            this.state.unfoldedLineIds.push(line.real_line_id);
        }
        if (!line._fetched) {
            // First time this line is unfolded under the current filters:
            // its children weren't returned by the last fetch, so go get them.
            await this.loadReport();
        }
    }

    async onCellClick(line, column, period) {
        if (column.value === null || column.value === undefined) {
            return;
        }
        await this.openJournalItems(line, column.expression_label, period);
    }

    toggleMenu(line) {
        this.state.openMenuLineId = this.state.openMenuLineId === line.id ? null : line.id;
    }

    async onOpenJournalItems(line) {
        this.state.openMenuLineId = null;
        const lastColumn = (this.state.report.columns || []).at(-1);
        // Kebab menu isn't tied to a specific period column - always drills
        // into the primary (first, non-comparison) period.
        await this.openJournalItems(line, lastColumn ? lastColumn.expression_label : null);
    }

    async openJournalItems(line, expressionLabel, period) {
        if (!expressionLabel) {
            return;
        }
        const options = this.buildOptions();
        if (period) {
            options.date_from = period.date_from;
            options.date_to = period.date_to;
        }
        const params = {
            options,
            expression_label: expressionLabel,
        };
        if (line.account_id) {
            params.account_id = line.account_id;
        }
        const action = await this.orm.call(
            "account.report.line",
            "action_get_drilldown",
            [[line.real_line_id]],
            params,
        );
        this.actionService.doAction(action);
    }

    async onOpenGeneralLedger(line) {
        this.state.openMenuLineId = null;
        const glReportId = this.state.report.general_ledger_report_id;
        if (!glReportId || !line.account_id) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.client",
            tag: "account_report_community",
            name: "General Ledger",
            context: {
                report_id: glReportId,
                focus_account_id: line.account_id,
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
            },
        });
    }

    // -- General Ledger ---------------------------------------------------
    // rendered by general_ledger_table.xml's GeneralLedgerLines template.

    toggleGeneralLedgerGroup(line) {
        line.unfolded = !line.unfolded;
    }

    async toggleGeneralLedgerAccount(line) {
        if (line.unfolded) {
            // Folding never needs new data - just hide what's already rendered.
            line.unfolded = false;
            const index = this.state.unfoldedLineIds.indexOf(line.account_id);
            if (index !== -1) {
                this.state.unfoldedLineIds.splice(index, 1);
            }
            return;
        }
        line.unfolded = true;
        if (!this.state.unfoldedLineIds.includes(line.account_id)) {
            this.state.unfoldedLineIds.push(line.account_id);
        }
        if (!line._fetched) {
            // First time this account is unfolded under the current filters:
            // its journal items weren't returned by the last fetch, so go get them.
            await this.loadReport();
        }
    }

    // -- Partner Ledger & Aged Receivable/Payable -------------------------
    // Both group by partner_id (partner_ledger_table.xml /
    // aged_balance_table.xml), so they share this fold/drill-down logic.

    async togglePartnerLedgerPartner(line) {
        if (line.unfolded) {
            // Folding never needs new data - just hide what's already rendered.
            line.unfolded = false;
            const index = this.state.unfoldedLineIds.indexOf(line.partner_id);
            if (index !== -1) {
                this.state.unfoldedLineIds.splice(index, 1);
            }
            return;
        }
        line.unfolded = true;
        if (!this.state.unfoldedLineIds.includes(line.partner_id)) {
            this.state.unfoldedLineIds.push(line.partner_id);
        }
        if (!line._fetched) {
            // First time this partner is unfolded under the current filters:
            // their journal items weren't returned by the last fetch, so go get them.
            await this.loadReport();
        }
    }

    onOpenPartnerJournalItems(line) {
        // Unlike the ledger view itself (receivable/payable only), this
        // opens every journal item for the partner regardless of account -
        // still scoped to the currently selected date range/journal/
        // posted-vs-all filters, since that's the period the user is
        // actually looking at.
        const domain = [["partner_id", "=", line.partner_id]];
        if (this.state.dateFrom) {
            domain.push(["date", ">=", this.state.dateFrom]);
        }
        if (this.state.dateTo) {
            domain.push(["date", "<=", this.state.dateTo]);
        }
        if (!this.state.allEntries) {
            domain.push(["parent_state", "=", "posted"]);
        }
        if (this.state.journalIds.length) {
            domain.push(["journal_id", "in", [...this.state.journalIds]]);
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `${line.name} — Journal Items`,
            res_model: "account.move.line",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain,
        });
    }

    // -- Tax Report --------------------------------------------------------
    // rendered by tax_report_table.xml's TaxReportLines template.

    async toggleTaxReportTax(line) {
        if (line.unfolded) {
            line.unfolded = false;
            const index = this.state.unfoldedLineIds.indexOf(line.tax_id);
            if (index !== -1) {
                this.state.unfoldedLineIds.splice(index, 1);
            }
            return;
        }
        line.unfolded = true;
        if (!this.state.unfoldedLineIds.includes(line.tax_id)) {
            this.state.unfoldedLineIds.push(line.tax_id);
        }
        if (!line._fetched) {
            await this.loadReport();
        }
    }

    onOpenTaxJournalItems(line) {
        const domain = [["tax_line_id", "=", line.tax_id]];
        if (this.state.dateFrom) {
            domain.push(["date", ">=", this.state.dateFrom]);
        }
        if (this.state.dateTo) {
            domain.push(["date", "<=", this.state.dateTo]);
        }
        if (!this.state.allEntries) {
            domain.push(["parent_state", "=", "posted"]);
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `${line.name} — Journal Items`,
            res_model: "account.move.line",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain,
        });
    }

    // -- Journal Report ----------------------------------------------------
    // rendered by journal_report_table.xml's JournalReportLines template.

    async toggleJournalReportJournal(line) {
        if (line.unfolded) {
            line.unfolded = false;
            const index = this.state.unfoldedLineIds.indexOf(line.journal_id);
            if (index !== -1) {
                this.state.unfoldedLineIds.splice(index, 1);
            }
            return;
        }
        line.unfolded = true;
        if (!this.state.unfoldedLineIds.includes(line.journal_id)) {
            this.state.unfoldedLineIds.push(line.journal_id);
        }
        if (!line._fetched) {
            await this.loadReport();
        }
    }

    // -- shared "Load more" pagination (any report's raw journal-item rows) -
    // One group_id field per report_handler (account_id/partner_id/tax_id/
    // journal_id); GL and Partner Ledger also carry a running_balance that
    // has to be continued from the last row already on screen, and Aged
    // Balance's server-side cursor sorts by due date rather than plain
    // date, so it needs its own extra param. Keyset pagination (based on
    // the last row's own date/id, not an OFFSET count) so "Load more"
    // stays equally fast no matter how many pages came before it.

    async loadMoreAmlRows(line) {
        const rows = line.aml_rows;
        const lastRow = rows[rows.length - 1];
        if (!lastRow) {
            return;
        }
        const handler = this.state.report.report_handler;
        const groupIdByHandler = {
            general_ledger: line.account_id,
            partner_ledger: line.partner_id,
            aged_partner_balance: line.partner_id,
            tax_report: line.tax_id,
            journal_report: line.journal_id,
        };
        const params = {
            options: this.buildOptions(),
            group_id: groupIdByHandler[handler],
            after_id: lastRow.id,
            after_date: lastRow.date,
        };
        if (handler === "general_ledger" || handler === "partner_ledger") {
            params.after_running_balance = lastRow.running_balance;
        }
        if (handler === "aged_partner_balance") {
            params.after_maturity = lastRow.due_date;
        }

        this.state.loadingMoreLineId = line.id;
        try {
            const result = await this.orm.call(
                "account.report",
                "action_get_more_aml_rows",
                [[this.reportId]],
                params,
            );
            line.aml_rows.push(...result.aml_rows);
            line.aml_rows_has_more = result.aml_rows_has_more;
        } finally {
            this.state.loadingMoreLineId = null;
        }
    }

    // -- shared navigation (any report's raw journal-item rows) ----------

    onOpenMove(row) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: row.move_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("account_report_community", AccountReportAction);
