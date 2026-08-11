# -*- coding: utf-8 -*-
import logging
from odoo.http import request
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ir_model_access(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.su', 'model', 'mode')
    def check(self, model, mode='read', raise_exception=True):
        # Bypass base ACL when an access management rule grants rights
        # (dynamic per-user access rights, applied before base ACL).
        try:
            value = self._cr.execute(
                """SELECT value from ir_config_parameter where key='uninstall_simplify_access_management' """)
            value = self._cr.fetchone()
            if not value:
                if model:
                    self._cr.execute("SELECT id FROM ir_model WHERE model='" + model + "'")
                    model_numeric_id = self._cr.fetchone()[0]
                    if model_numeric_id and isinstance(model_numeric_id, int) and self.env.user:
                        self._cr.execute("""
                                        SELECT dm.id
                                        FROM access_domain_ah as dm
                                        WHERE dm.model_id=%s AND dm.access_management_id 
                                        IN (SELECT am.id 
                                            FROM access_management as am 
                                            WHERE active='t' AND am.id 
                                            IN (SELECT amusr.access_management_id
                                                FROM access_management_users_rel_ah as amusr
                                                WHERE amusr.user_id=%s))
                                        """, [model_numeric_id, self.env.user.id])

                        access_domain_ah_ids = self.env['access.domain.ah'].browse(
                            row[0] for row in self._cr.fetchall()).filtered(
                            lambda line: self.env.company in line.access_management_id.company_ids)
                        if access_domain_ah_ids:
                            return True
        except Exception:
            _logger.warning("Error while checking access management rights", exc_info=True)

        r = super().check(model, mode, raise_exception=raise_exception)

        # Readonly users (granted access through the base ACLs) are not allowed
        # to create/write/delete anything from the web interface.
        try:
            read_value = True
            self._cr.execute("SELECT state FROM ir_module_module WHERE name='simplify_access_management'")
            data = self._cr.fetchone() or False
            if data and data[0] != 'installed':
                read_value = False
            if r and self.env.user.id and read_value and request.httprequest.cookies.get('cids'):
                cids = request.httprequest.cookies.get('cids').split(',')[0] or self.env.company.id
                self._cr.execute("""
                                SELECT am.id FROM access_management am
                                JOIN access_management_comapnay_rel ac ON ac.access_management_id = am.id
                                JOIN access_management_users_rel_ah au ON au.access_management_id = am.id
                                WHERE ac.company_id=%s AND au.user_id=%s AND am.active='t' AND am.readonly='t'
                                """, (int(cids), self.env.user.id))
                if self._cr.fetchone():
                    if mode != 'read':
                        return False
        except Exception:
            _logger.warning("Error while applying readonly access management rule", exc_info=True)

        return r
