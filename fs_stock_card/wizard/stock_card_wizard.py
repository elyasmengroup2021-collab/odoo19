import io
import base64
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class StockCardWizard(models.TransientModel):
    _name = 'stock.card.wizard'
    _description = 'Stock Card Report Wizard'

    date_from = fields.Date(
        string='Start Date',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='End Date',
        required=True,
        default=fields.Date.today
    )
    
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
        domain="[('usage', 'in', ['internal', 'transit'])]",
        required=True,
    )
    include_child_locations = fields.Boolean(
        string='Include Child Locations',
        default=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    filter_by = fields.Selection([
        ('product', 'Product'),
        ('category', 'Product Category'),
    ], string='Filter By', default='product', required=True)
    
    include_zero_movements = fields.Boolean(
        string='Include Zero Movements',
        default=False
    )
    
    group_by = fields.Selection([
        ('product', 'Product'),
        ('category', 'Category'),
    ], string='Group By', default='product', required=True)
    
    product_ids = fields.Many2many(
        'product.product',
        'stock_card_wizard_product_rel',
        'wizard_id',
        'product_id',
        string='Products',
        domain="[('type', '=', 'consu')]"
    )
    categ_ids = fields.Many2many(
        'product.category',
        'stock_card_wizard_category_rel',
        'wizard_id',
        'categ_id',
        string='Product Categories'
    )
    
    line_ids = fields.One2many('stock.card.line', 'wizard_id', string='Stock Card Lines')

    @api.onchange('location_id')
    def _onchange_location_id(self):
        if self.location_id:
            self.company_id = self.location_id.company_id or self.env.company

    @api.onchange('filter_by')
    def _onchange_filter_by(self):
        if self.filter_by == 'product':
            self.categ_ids = False
        else:
            self.product_ids = False

    def _get_locations(self):
        """Get all locations including children if specified"""
        self.ensure_one()
        if self.include_child_locations:
            return self.env['stock.location'].search([
                ('id', 'child_of', self.location_id.id),
                ('usage', 'in', ['internal', 'transit'])
            ])
        return self.location_id

    def _get_products(self):
        """Get products based on filter criteria"""
        self.ensure_one()
        domain = [('type', '=', 'consu')]
        
        if self.filter_by == 'product' and self.product_ids:
            domain.append(('id', 'in', self.product_ids.ids))
        elif self.filter_by == 'category' and self.categ_ids:
            domain.append(('categ_id', 'child_of', self.categ_ids.ids))
        
        return self.env['product.product'].search(domain, order='name')

    def _get_opening_balance(self, product, locations):
        """Calculate opening balance for a product before date_from"""
        self.ensure_one()
        location_ids = locations.ids
        
        query = """
            SELECT 
                COALESCE(SUM(CASE 
                    WHEN sml.location_dest_id IN %s AND sml.location_id NOT IN %s 
                    THEN sml.quantity ELSE 0 END), 0) AS qty_in,
                COALESCE(SUM(CASE 
                    WHEN sml.location_id IN %s AND sml.location_dest_id NOT IN %s 
                    THEN sml.quantity ELSE 0 END), 0) AS qty_out
            FROM stock_move_line sml
            JOIN stock_move sm ON sm.id = sml.move_id
            WHERE sml.state = 'done'
            AND sml.product_id = %s
            AND sml.date < %s
            AND (sml.location_id IN %s OR sml.location_dest_id IN %s)
        """
        
        self.env.cr.execute(query, (
            tuple(location_ids), tuple(location_ids),
            tuple(location_ids), tuple(location_ids),
            product.id, self.date_from,
            tuple(location_ids), tuple(location_ids)
        ))
        
        result = self.env.cr.fetchone()
        qty_in = result[0] if result else 0
        qty_out = result[1] if result else 0
        
        return qty_in - qty_out

    def _get_opening_value(self, product, opening_qty):
        """Calculate opening value based on costing method"""
        self.ensure_one()
        if opening_qty == 0:
            return 0.0
        
        cost = product.standard_price
        return opening_qty * cost

    def _get_transactions(self, product, locations):
        """Get all stock movements for a product within date range"""
        self.ensure_one()
        location_ids = locations.ids
        
        domain = [
            ('state', '=', 'done'),
            ('product_id', '=', product.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            '|',
            ('location_id', 'in', location_ids),
            ('location_dest_id', 'in', location_ids),
        ]
        
        move_lines = self.env['stock.move.line'].search(domain, order='date, id')
        return move_lines

    def _prepare_line_vals(self, line_type, product, **kwargs):
        """Prepare values for stock card line"""
        vals = {
            'wizard_id': self.id,
            'line_type': line_type,
            'product_id': product.id if product else False,
            'date': kwargs.get('date'),
            'reference': kwargs.get('reference', ''),
            'source_document': kwargs.get('source_document', ''),
            'partner_id': kwargs.get('partner_id'),
            'qty_in': kwargs.get('qty_in', 0.0),
            'qty_out': kwargs.get('qty_out', 0.0),
            'balance': kwargs.get('balance', 0.0),
            'initial_balance': kwargs.get('initial_balance', 0.0),
            'unit_cost': kwargs.get('unit_cost', 0.0),
            'value_in': kwargs.get('value_in', 0.0),
            'value_out': kwargs.get('value_out', 0.0),
            'balance_value': kwargs.get('balance_value', 0.0),
            'location_id': kwargs.get('location_id'),
            'location_dest_id': kwargs.get('location_dest_id'),
            'move_id': kwargs.get('move_id'),
            'move_line_id': kwargs.get('move_line_id'),
            'sequence': kwargs.get('sequence', 10),
            'group_name': kwargs.get('group_name', ''),
            'transaction_count': kwargs.get('transaction_count', 0),
        }
        return vals

    def _generate_stock_card_data(self):
        """Generate stock card data for all selected products"""
        self.ensure_one()
        self.line_ids.unlink()
        
        locations = self._get_locations()
        products = self._get_products()
        
        if not products:
            raise UserError(_('No products found matching the criteria.'))
        
        lines_data = []
        location_ids = locations.ids
        
        grouped_products = {}
        if self.group_by == 'category':
            for product in products:
                categ = product.categ_id
                if categ.id not in grouped_products:
                    grouped_products[categ.id] = {
                        'name': categ.complete_name,
                        'products': []
                    }
                grouped_products[categ.id]['products'].append(product)
        else:
            for product in products:
                grouped_products[product.id] = {
                    'name': product.display_name,
                    'products': [product]
                }
        
        sequence = 0
        for group_key, group_data in grouped_products.items():
            group_products = group_data['products']
            group_has_movements = False
            group_lines = []
            
            for product in group_products:
                opening_qty = self._get_opening_balance(product, locations)
                opening_value = self._get_opening_value(product, opening_qty)
                
                transactions = self._get_transactions(product, locations)
                
                if not transactions and not self.include_zero_movements and opening_qty == 0:
                    continue
                
                group_has_movements = True
                running_balance = opening_qty
                running_value = opening_value
                
                sequence += 1
                group_lines.append(self._prepare_line_vals(
                    'opening',
                    product,
                    date=self.date_from,
                    reference='Opening Balance',
                    balance=opening_qty,
                    balance_value=opening_value,
                    sequence=sequence,
                ))
                
                for move_line in transactions:
                    qty_in = 0.0
                    qty_out = 0.0
                    
                    if move_line.location_dest_id.id in location_ids and move_line.location_id.id not in location_ids:
                        qty_in = move_line.quantity
                    elif move_line.location_id.id in location_ids and move_line.location_dest_id.id not in location_ids:
                        qty_out = move_line.quantity
                    elif move_line.location_id.id in location_ids and move_line.location_dest_id.id in location_ids:
                        continue
                    
                    if qty_in == 0 and qty_out == 0:
                        continue
                    
                    initial_balance = running_balance
                    running_balance += qty_in - qty_out
                    
                    unit_cost = product.standard_price
                    value_in = qty_in * unit_cost
                    value_out = qty_out * unit_cost
                    running_value += value_in - value_out
                    
                    move = move_line.move_id
                    reference = move.picking_id.name if move.picking_id else move.name
                    source_document = move.origin or ''
                    
                    sequence += 1
                    group_lines.append(self._prepare_line_vals(
                        'transaction',
                        product,
                        date=move_line.date.date() if move_line.date else False,
                        reference=reference,
                        source_document=source_document,
                        partner_id=move.partner_id.id if move.partner_id else False,
                        initial_balance=initial_balance,
                        qty_in=qty_in,
                        qty_out=qty_out,
                        balance=running_balance,
                        unit_cost=unit_cost,
                        value_in=value_in,
                        value_out=value_out,
                        balance_value=running_value,
                        location_id=move_line.location_id.id,
                        location_dest_id=move_line.location_dest_id.id,
                        move_id=move.id,
                        move_line_id=move_line.id,
                        sequence=sequence,
                    ))
                
                sequence += 1
                group_lines.append(self._prepare_line_vals(
                    'closing',
                    product,
                    date=self.date_to,
                    reference='Closing Balance',
                    initial_balance=opening_qty,
                    balance=running_balance,
                    balance_value=running_value,
                    sequence=sequence,
                ))
            
            if group_has_movements or self.include_zero_movements:
                if self.group_by == 'category' and len(group_products) > 1:
                    sequence += 1
                    lines_data.append(self._prepare_line_vals(
                        'group_header',
                        None,
                        group_name=f"{group_data['name']} ({len(group_lines)})",
                        transaction_count=len(group_lines),
                        sequence=sequence,
                    ))
                
                lines_data.extend(group_lines)
        
        if not lines_data:
            raise UserError(_('No stock movements found for the selected criteria.'))
        
        self.env['stock.card.line'].create(lines_data)
        
        return True

    def action_view_report(self):
        """Generate and view the stock card report"""
        self.ensure_one()
        self._generate_stock_card_data()
        
        action = {
            'name': _('Stock Card Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.card.line',
            'view_mode': 'list,pivot',
            'views': [
                (self.env.ref('fs_stock_card.view_stock_card_line_list').id, 'list'),
                (self.env.ref('fs_stock_card.view_stock_card_line_pivot').id, 'pivot'),
            ],
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'search_default_group_by_product': self.group_by == 'product',
                'search_default_group_by_category': self.group_by == 'category',
            },
            'target': 'current',
        }
        
        return action

    def action_generate_pdf(self):
        """Generate PDF report"""
        self.ensure_one()
        self._generate_stock_card_data()
        
        return self.env.ref('fs_stock_card.action_report_stock_card').report_action(self)

    def action_generate_excel(self):
        """Generate Excel report"""
        self.ensure_one()
        
        if not xlsxwriter:
            raise UserError(_('xlsxwriter library is required for Excel export. Please install it.'))
        
        self._generate_stock_card_data()
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Stock Card')
        
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#875A7B',
            'font_color': 'white',
            'border': 1,
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
        })
        
        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd',
            'align': 'center',
            'border': 1,
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right',
            'border': 1,
        })
        
        text_format = workbook.add_format({
            'align': 'left',
            'border': 1,
        })
        
        opening_format = workbook.add_format({
            'bg_color': '#E8F5E9',
            'align': 'left',
            'border': 1,
            'italic': True,
        })
        
        closing_format = workbook.add_format({
            'bg_color': '#E3F2FD',
            'bold': True,
            'align': 'left',
            'border': 1,
        })
        
        worksheet.merge_range('A1:H1', 'Stock Card Summary Report', title_format)
        worksheet.write('A2', f"Period: {self.date_from} to {self.date_to}")
        worksheet.write('A3', f"Location: {self.location_id.complete_name}")
        worksheet.write('A4', f"Company: {self.company_id.name}")
        
        headers = [
            'Product', 'Category', 'Initial Balance', 'Total In', 'Total Out', 
            'Closing Balance', 'Unit Cost', 'Balance Value'
        ]
        
        col_widths = [35, 25, 15, 15, 15, 15, 15, 18]
        for col, width in enumerate(col_widths):
            worksheet.set_column(col, col, width)
        
        row = 5
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        closing_lines = self.line_ids.filtered(lambda l: l.line_type == 'closing')
        transaction_lines = self.line_ids.filtered(lambda l: l.line_type == 'transaction')
        
        row += 1
        for line in closing_lines:
            product_transactions = transaction_lines.filtered(lambda l: l.product_id == line.product_id)
            total_in = sum(product_transactions.mapped('qty_in'))
            total_out = sum(product_transactions.mapped('qty_out'))
            
            worksheet.write(row, 0, line.product_id.display_name, text_format)
            worksheet.write(row, 1, line.categ_id.complete_name or '', text_format)
            worksheet.write(row, 2, line.initial_balance, number_format)
            worksheet.write(row, 3, total_in, number_format)
            worksheet.write(row, 4, total_out, number_format)
            worksheet.write(row, 5, line.balance, number_format)
            worksheet.write(row, 6, line.product_id.standard_price, number_format)
            worksheet.write(row, 7, line.balance_value, number_format)
            row += 1
        
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F3E5F5',
            'border': 1,
            'num_format': '#,##0.00',
        })
        
        total_initial = sum(closing_lines.mapped('initial_balance'))
        total_in = sum(transaction_lines.mapped('qty_in'))
        total_out = sum(transaction_lines.mapped('qty_out'))
        total_balance = sum(closing_lines.mapped('balance'))
        total_balance_value = sum(closing_lines.mapped('balance_value'))
        
        row += 1
        worksheet.write(row, 0, 'TOTALS:', total_format)
        worksheet.write(row, 1, '', total_format)
        worksheet.write(row, 2, total_initial, total_format)
        worksheet.write(row, 3, total_in, total_format)
        worksheet.write(row, 4, total_out, total_format)
        worksheet.write(row, 5, total_balance, total_format)
        worksheet.write(row, 6, '', total_format)
        worksheet.write(row, 7, total_balance_value, total_format)
        
        workbook.close()
        output.seek(0)
        
        excel_data = base64.b64encode(output.read())
        output.close()
        
        attachment = self.env['ir.attachment'].create({
            'name': f'Stock_Card_Report_{self.date_from}_{self.date_to}.xlsx',
            'type': 'binary',
            'datas': excel_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
