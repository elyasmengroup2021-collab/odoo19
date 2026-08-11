from odoo import http
from odoo.exceptions import UserError
from odoo.addons.web.controllers.export import Export
from odoo.http import request

class Export(Export):

    def _get_hidden_field_names(self, model):
        invisible_field_ids = request.env['hide.field'].search(
            [('access_management_id.company_ids', 'in', request.env.company.id),
             ('model_id.model', '=', model), ('access_management_id.active', '=', True),
             ('access_management_id.user_ids', 'in', request.env.user.id),
             ('invisible', '=', True)])
        return {invisible_field.name for invisible_field in invisible_field_ids.field_id}

    def _filter_hidden_fields(self, field_info, model):
        hidden_names = self._get_hidden_field_names(model)
        if not hidden_names:
            return field_info
        filtered = []
        for field_dict in field_info:
            segments = (field_dict.get('id') or '').split('/')
            if any(segment in hidden_names for segment in segments):
                continue
            filtered.append(field_dict)
        return filtered

    def get_fields(self, model, domain, prefix='', parent_name='',
                   import_compat=True, parent_field_type=None,
                   parent_field=None, exclude=None):
        result = super().get_fields(
            model, domain, prefix=prefix, parent_name=parent_name,
            import_compat=import_compat, parent_field_type=parent_field_type,
            parent_field=parent_field, exclude=exclude)
        return self._filter_hidden_fields(result, model)

    def fields_info(self, model, export_fields):
        result = super().fields_info(model, export_fields)
        return self._filter_hidden_fields(result, model)
