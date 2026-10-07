from odoo import models, _
from odoo.exceptions import UserError
from odoo.fields import Domain


class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    def _build_line_row(self, options_list):
        """Build this line's JSON row, recursing into children when unfolded.

        `options_list` is [current_period_options, previous_period_options, ...]
        (see account.report._get_comparison_options_list) -- one full options
        dict per period the report should display. Comparison periods are
        just extra entries in this list; unfold state, search, journal
        filter etc. are shared across all of them (options_list[0] is
        authoritative for anything that isn't period-specific).

        Lines with a `groupby` value take a different path (see
        `_build_groupby_row`) since their rows aren't static
        account.report.line records but one synthesized row per group key.
        """
        self.ensure_one()
        if self.groupby:
            return self._build_groupby_row(options_list)

        periods = self._compute_periods(options_list)
        force_fold = options_list[0].get('collapse_all')
        unfolded = False if force_fold else (
            (not self.foldable)
            or options_list[0].get('export_mode')
            or options_list[0].get('unfold_all')
            or (self.id in (options_list[0].get('unfolded_line_ids') or []))
        )
        children = []
        if self.children_ids and unfolded:
            children = [child._build_line_row(options_list) for child in self.children_ids.sorted('sequence')]

        return {
            'id': self.id,
            'real_line_id': self.id,
            'name': self.name,
            'code': self.code,
            'level': self.hierarchy_level,
            'foldable': self.foldable,
            'unfolded': unfolded,
            'has_children': bool(self.children_ids),
            'periods': periods,
            'children': children,
        }

    def _compute_periods(self, options_list, extra_domain=None):
        self.ensure_one()
        periods = []
        for options in options_list:
            columns = []
            for column in self.report_id._get_render_columns(options):
                expression = self.expression_ids.filtered(lambda e: e.label == column.get('source_expression_label', column['expression_label']))
                eval_options = dict(options)
                if column.get('analytic_dimension_ids') is not None:
                    eval_options['_analytic_dimension_ids'] = column['analytic_dimension_ids']
                value = expression[0]._evaluate(eval_options, extra_domain=extra_domain)[0] if expression else 0.0
                columns.append({'expression_label': column['expression_label'], 'value': value})
            periods.append({
                'label': options.get('period_label', ''),
                'date_from': options.get('date_from'),
                'date_to': options.get('date_to'),
                'columns': columns,
            })
        return periods

    def _compute_periods_by_account(self, options_list, account_ids):
        """Batched counterpart to calling _compute_periods(extra_domain=...)
        once per account: evaluates every column's expression once across
        *all* account_ids per period (one query each, via
        account.report.expression._evaluate_batch_by_account), instead of
        once per account. For a category with a few hundred accounts and a
        handful of columns, that's the difference between a handful of
        queries and hundreds.

        :return: {account_id: [period_dict, ...]} on success, or None if
                 any column's expression can't be batched (anything other
                 than the 'domain' engine) - the caller should then fall
                 back to _compute_periods() once per account, which stays
                 correct either way, just slower.
        """
        self.ensure_one()
        columns = self.report_id._get_render_columns(options_list[0])

        # values_by_period[i][expression_label] = {account_id: value}, one
        # entry per period in options_list.
        values_by_period = []
        for options in options_list:
            values_by_label = {}
            for column in columns:
                expression = self.expression_ids.filtered(lambda e: e.label == column.get('source_expression_label', column['expression_label']))
                if not expression:
                    values_by_label[column['expression_label']] = {}
                    continue
                eval_options = dict(options)
                if column.get('analytic_dimension_ids') is not None:
                    eval_options['_analytic_dimension_ids'] = column['analytic_dimension_ids']
                batch = expression[0]._evaluate_batch_by_account(eval_options, account_ids)
                if batch is None:
                    return None
                values_by_label[column['expression_label']] = batch
            values_by_period.append(values_by_label)

        result = {}
        for account_id in account_ids:
            periods = []
            for options, values_by_label in zip(options_list, values_by_period):
                periods.append({
                    'label': options.get('period_label', ''),
                    'date_from': options.get('date_from'),
                    'date_to': options.get('date_to'),
                    'columns': [
                        {
                            'expression_label': column['expression_label'],
                            'value': values_by_label[column['expression_label']].get(account_id, 0.0),
                        }
                        for column in columns
                    ],
                })
            result[account_id] = periods
        return result

    def _build_groupby_row(self, options_list):
        """Used both by Trial Balance's single top-level "Accounts" line
        (foldable=False, always expanded - it IS the account-level report)
        and by Balance Sheet/P&L leaf lines (foldable=True), which stay
        collapsed to a single category total by default and expand into
        their constituent accounts - each carrying its own `account_id`,
        which is what makes the General Ledger/Journal Items drill-down menu
        appear on them, same as it does for Trial Balance's account rows.
        """
        self.ensure_one()
        if self.groupby != 'account_id':
            raise UserError(_(
                "Report line '%s' uses groupby '%s', which isn't supported yet "
                "(only 'account_id' is implemented).", self.name, self.groupby,
            ))

        main_options = options_list[0]
        force_fold = main_options.get('collapse_all') and not main_options.get('hierarchy_and_subtotals')
        unfolded = False if force_fold else (
            (not self.foldable)
            or main_options.get('export_mode')
            or main_options.get('unfold_all')
            or (self.id in (main_options.get('unfolded_line_ids') or []))
        )

        children = []
        if unfolded:
            account_domain = []
            search = main_options.get('search')
            if search:
                account_domain += ['|', ('code', 'ilike', search), ('name', 'ilike', search)]
            accounts = self.env['account.account'].search(account_domain, order='code')
            batched_periods = self._compute_periods_by_account(options_list, accounts.ids)
            account_rows = []
            for account in accounts:
                periods = (batched_periods[account.id] if batched_periods is not None else
                           self._compute_periods(options_list, extra_domain=[('account_id', '=', account.id)]))
                if any(col['value'] for period in periods for col in period['columns']):
                    account_rows.append({'id': f'{self.id}-account-{account.id}', 'real_line_id': self.id,
                        'account_id': account.id, 'account_group_id': account.group_id.id if account.group_id else False, 'name': f'{account.code} {account.name}', 'code': account.code,
                        'level': self.hierarchy_level + 1, 'foldable': False, 'unfolded': True,
                        'has_children': False, 'periods': periods, 'children': []})
            children = self._build_account_group_rows(account_rows, options_list) if main_options.get('hierarchy_and_subtotals') else account_rows
        # The summary row's own total - the line's own expression(s)
        # evaluated with no extra_domain, i.e. across every account, not
        # just one. This is the figure that matters when the row is
        # collapsed (a Balance Sheet category total, or Trial Balance's
        # grand Total row), and it's independent of whichever individual
        # accounts happen to be listed below it once expanded.
        periods = self._compute_periods(options_list)

        return {
            'id': self.id,
            'real_line_id': self.id,
            'name': self.name,
            'code': self.code,
            'level': self.hierarchy_level,
            'foldable': self.foldable,
            'unfolded': unfolded,
            'has_children': True,
            'summary_at_bottom': self.report_id.name == 'Trial Balance' and (self.code == 'TBALL' or self.name in ('Accounts', 'Total')),
            'periods': periods,
            'children': children,
        }

    def _build_account_group_rows(self, account_rows, options_list):
        """Build nested account.group subtotal rows using Odoo code ranges."""
        Group = self.env['account.group']
        groups = Group.search([], order='parent_id, code_prefix_start, name')
        if not groups:
            return account_rows
        def matches(group, code):
            start = (group.code_prefix_start or '').strip()
            end = (group.code_prefix_end or '').strip() or start
            if not start or not code or len(start) != len(end):
                return False
            prefix = str(code)[:len(start)]
            return start <= prefix <= end
        def depth(group):
            value = 0
            seen = set()
            while group and group.id not in seen:
                seen.add(group.id)
                value += 1
                group = group.parent_id
            return value
        def is_descendant(group, ancestor):
            seen = set()
            while group and group.id not in seen:
                if group.id == ancestor.id:
                    return True
                seen.add(group.id)
                group = group.parent_id
            return False
        owner = {}
        for row in account_rows:
            group = groups.browse(row.get('account_group_id')) if row.get('account_group_id') else groups.browse()
            if not group:
                candidates = groups.filtered(lambda g: matches(g, row['code']))
                group = max(candidates, key=depth) if candidates else groups.browse()
            if group:
                owner[row['id']] = group
        if not owner: return account_rows
        used_ids = {g.id for g in owner.values()}
        changed = True
        while changed:
            changed = False
            for g in groups:
                if g.id in used_ids and g.parent_id and g.parent_id.id not in used_ids:
                    used_ids.add(g.parent_id.id)
                    changed = True
        used = groups.filtered(lambda g: g.id in used_ids)
        children_by_parent = {}
        for g in used: children_by_parent.setdefault(g.parent_id.id if g.parent_id else False, []).append(g)
        by_code = {r['id']: r for r in account_rows}
        def subtotal(rows):
            periods=[]
            for i, _opts in enumerate(options_list):
                cols=[]
                render_columns = self.report_id._get_render_columns(options_list[i])
                for col in render_columns:
                    vals=[c['value'] for r in rows for c in r['periods'][i]['columns'] if c['expression_label']==col['expression_label'] and c['value'] is not None]
                    cols.append({'expression_label': col['expression_label'], 'value': sum(vals) if vals else 0.0})
                periods.append({'date_from': options_list[i].get('date_from'), 'date_to': options_list[i].get('date_to'), 'columns': cols})
            return periods
        def make(g, level):
            direct=[r for row_id,r in by_code.items() if owner.get(row_id)==g]
            nested=[make(child,level+1) for child in sorted(children_by_parent.get(g.id,[]), key=lambda x:(x.code_prefix_start or '',x.name))]
            rows=nested+sorted(direct,key=lambda r:r['code'])
            descendants=[r for row_id,r in by_code.items()
                         if owner.get(row_id) and is_descendant(owner[row_id], g)]
            return {'id':f'{self.id}-group-{g.id}','real_line_id':self.id,'group_id':g.id,
                'name':f'{g.code_prefix_start or ""} {g.name}'.strip(),'code':g.code_prefix_start,
                'level':level,'foldable':bool(rows),'unfolded':not options_list[0].get('collapse_all'),'has_children':bool(rows),
                'periods':subtotal(descendants),'children':rows}
        result=[make(g,self.hierarchy_level+1) for g in sorted(children_by_parent.get(False,[]),key=lambda x:(x.code_prefix_start or '',x.name))]
        result += sorted([r for row_id,r in by_code.items() if row_id not in owner],key=lambda r:r['code'])
        return result or account_rows

    def _get_drilldown_domain(self, options, expression_label, account_id=None):
        self.ensure_one()
        expression = self.expression_ids.filtered(lambda e: e.label == expression_label)
        if not expression:
            return [('id', '=', 0)]

        extra_domain = [('account_id', '=', account_id)] if account_id else None
        _value, domains = expression[0]._evaluate(options, extra_domain=extra_domain)
        if not domains:
            return [('id', '=', 0)]

        # Domain.OR (not a hand-rolled ['|', ...] splice): each domain in
        # `domains` can itself carry several implicitly-ANDed conditions
        # (company/posted-state/date/account_type, ...), and a bare '|'
        # prefix only combines the next *two* leaves in polish notation, not
        # two whole multi-condition lists - splicing '|' in front of them
        # silently produces the wrong boolean expression (this was the
        # cause of drilldown's journal-item list summing to something
        # other than the cell it was drilled down from, on any 'aggregation'
        # expression combining more than one sub-domain, e.g. Balance
        # Sheet's Total Assets = Current Assets + Non-current Assets).
        return list(Domain.OR(domains))

    def action_get_drilldown(self, options, expression_label, account_id=None):
        """Public RPC entry point used by the OWL frontend when a user
        clicks a report cell: returns an act_window opening the exact
        journal items that contributed to that cell's value. `options`
        here is always a single period's options (the one the clicked
        cell belongs to), never the comparison options_list."""
        self.ensure_one()
        resolved_options = self.report_id._get_default_options(options or {})
        domain = self._get_drilldown_domain(resolved_options, expression_label, account_id=account_id)
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} — {expression_label}',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
        }
