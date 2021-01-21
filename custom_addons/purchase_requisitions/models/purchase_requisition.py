from datetime import datetime

from odoo import models, fields, api, _


def model_data(obj):
    fields_dict = {}
    for key in obj.fields_get():
        fields_dict[key] = obj[key]
    return fields_dict


class PurchaseRequisition(models.Model):
    _name = 'minhduc.purchase.requisition'
    _description = "Purchase Requisition"
    _rec_name = 'sequence'
    _order = 'sequence asc'

    sequence = fields.Char(string='Sequence', readonly=True, copy=False, index=True, default=lambda self: _('New'),
                           required=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    responsible_requisition_id = fields.Many2one('res.users', string='Requisition Reponsible')
    requisition_date = fields.Date('Requisition Date', required=True)
    received_date = fields.Date('Receive Date', required=True)
    requisition_deadline = fields.Date('Requisition DeadLine')
    company_id = fields.Many2one('res.company', string='Company', required=True)
    department_manager_id = fields.Many2one('res.users', string='Department Manager', copy=False)
    department_approval_date = fields.Date('Department Approve Date', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Approve By', copy=False)
    approved_date = fields.Date('Approved Date', readonly=True, copy=False)
    rejected_by_id = fields.Many2one('res.users', string='Rejected By')
    rejected_date = fields.Date('Rejected Date')
    state = fields.Selection([
        ('new', 'Draft'),
        ('department_approval', 'Waiting Department Approval'),
        ('approve_ur', 'Waiting User Approved'),
        ('approved', 'Approved'),
        ('po_created', 'Purchase Order Created'),
        ('received', 'Received'),
        ('cancel', 'Cancel')
    ], string='Status', index=True, readonly=True, default='new')
    requisition_line_ids = fields.One2many('requisition.line', 'requistion_id',
                                           string='Requisition Line ID')
    confirmed_by_id = fields.Many2one('res.users', string='Confirmed By', copy=False)
    confirmed_date = fields.Date(string='Confirmed Date', readonly=True, copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', string='Purchase Operation Type', required=True)
    choose_manual_location = fields.Boolean(string='Choose manual location')
    destination_location_id = fields.Many2one('stock.location', 'Destination Location')
    source_location_id = fields.Many2one('stock.location', 'Source Location')
    internal_picking_id = fields.Many2one('stock.picking.type', 'Internal picking type')
    internal_picking_count = fields.Integer('Internal Picking Count', compute='_get_internal_picking_count')
    purchase_order_count = fields.Integer('Purchase Order', compute='_get_purchase_order_count')

    # @api.onchange('company_id','picking_type_id','choose_manual_location')
    # def _checker(self):
    #     pass
    def _get_purchase_order_count(self):
        for rec in self:
            purchase_order_ids = self.env['purchase.order'].search([('po_requisition_ids', '=', rec.id)])
            rec.purchase_order_count = len(purchase_order_ids)

    def purchase_order_button(self):
        self.ensure_one()
        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'domain': [('po_requisition_ids', '=', self.id)]
        }

    def _get_internal_picking_count(self):
        for rec in self:
            picking_ids = self.env['stock.picking'].search([('req_picking_id', '=', rec.id)])
            rec.internal_picking_count = len(picking_ids)

    def internal_picking_button(self):
        self.ensure_one()
        return {
            'name': 'Internal Picking',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('req_picking_id', '=', self.id)],
        }

    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('code.purchase.requisition') or _('New')
        return super(PurchaseRequisition, self).create(vals)

    def confirm_requisition(self):
        for requisition in self:
            requisition.write({
                'state': 'department_approval',
                'confirmed_by_id': self.env.user.id,
                'confirmed_date': datetime.now()
            })

    def department_approve(self):
        for req in self:
            req.write(
                {
                    'state': 'approve_ur',
                    'department_manager_id': self.env.user.id,
                    'department_approval_date': datetime.now()
                }
            )

    def create_picking_po(self):
        for req in self:
            for line in req.requisition_line_ids:
                if line.requisition_action == 'purchase_order':
                    for vendor in line.vendor_id:
                        purchase_order = self.env['purchase.order'].search(
                            [('po_requisition_ids', '=', req.id), ('partner_id', '=', vendor.id)])
                        if purchase_order:
                            self.env['purchase.order.line'].create(
                                {
                                    'product_id': line.product_id.id,
                                    'name': line.description,
                                    'product_qty': line.qty,
                                    'price_unit': line.product_id.list_price,
                                    'order_id': purchase_order.id,
                                    'product_uom': line.uom_id.id,
                                    'date_planned': datetime.now()
                                }
                            )
                        else:
                            po = self.env['purchase.order'].create({
                                'partner_id': vendor.id,
                                'date_order': datetime.now(),
                                'po_requisition_ids': req.id,
                                'origin': req.sequence,
                                'state': 'draft',
                                'picking_type_id': req.picking_type_id.id
                            })
                            self.env['purchase.order.line'].create({
                                'product_id': line.product_id.id,
                                'name': line.description,
                                'product_qty': line.qty,
                                'price_unit': line.product_id.list_price,
                                'order_id': po.id,
                                'product_uom': line.uom_id.id,
                                'date_planned': datetime.now()
                            })
                else:
                    picking_type_id = None
                    if not req.choose_manual_location:
                        picking_type_id = req.internal_picking_id
                    else:
                        picking_type_id = self.env['stock.picking.type'].search(
                            [('code', '=', 'internal'), ('company_id', '=', req.company_id.id or False)],
                            order="id desc", limit=1)
                        if not picking_type_id:
                            picking_type_id = req.internal_picking_id
                    if line.vendor_id:
                        for vendor in line.vendor_id:
                            po = self.env['stock.picking'].search(
                                [('req_picking_id', '=', req.id), ('partner_id', '=', vendor.id)])
                            if po:
                                if req.choose_manual_location:
                                    picking_line = {
                                        'name': line.product_id.name,
                                        'product_id': line.product_id.id,
                                        'product_uom_qty': line.qty,
                                        'picking_id': picking_type_id.id,
                                        'product_uom': line.uom_id.id,
                                        'location_id': req.source_location_id.id,
                                        'location_dest_id': req.destination_location_id.id,
                                    }
                                else:
                                    picking_line = {
                                        'name': line.product_id.name,
                                        'product_id': line.product_id.id,
                                        'product_uom_qty': line.qty,
                                        'product_uom': line.uom_id.id,
                                        'picking_id': picking_type_id.id,
                                        'location_id': req.internal_picking_id.default_location_src_id.id,
                                        'location_dest_id': req.picking_type_id.default_location_dest_id.id,
                                    }
                                self.env['stock.move'].create(picking_line)
                            else:
                                if req.choose_manual_location:
                                    vals = {
                                        'partner_id': vendor.id,
                                        'picking_type_id': picking_type_id.id,
                                        'company_id': req.company_id.id,
                                        'req_picking_id': req.id,
                                        'origin': req.sequence,
                                        'location_id': req.source_location_id.id,
                                        'location_dest_id': req.destination_location_id.id,
                                    }
                                    stock_picking = self.env['stock.picking'].create(vals)
                                    pic_line_val = {
                                        'partner_id': vendor.id,
                                        'name': line.product_id.name,
                                        'product_id': line.product_id.id,
                                        'product_uom_qty': line.qty,
                                        'product_uom': line.uom_id.id,
                                        'location_id': req.source_location_id.id,
                                        'location_dest_id': req.destination_location_id.id,
                                        'picking_id': stock_picking.id,
                                        'origin': req.sequence,
                                    }
                                    self.env['stock.move'].create(pic_line_val)
                                else:
                                    vals = {
                                        'partner_id': vendor.id,
                                        'picking_type_id': picking_type_id.id,
                                        'company_id': req.company_id.id,
                                        'req_picking_id': req.id,
                                        'origin': req.sequence,
                                        'location_id': req.internal_picking_id.default_location_src_id.id,
                                        'location_dest_id': req.internal_picking_id.default_location_dest_id.id,
                                    }
                                    stock_picking = self.env['stock.picking'].create(vals)
                                    pic_line_val = {
                                        'partner_id': vendor.id,
                                        'name': line.product_id.name,
                                        'product_id': line.product_id.id,
                                        'product_uom_qty': line.qty,
                                        'product_uom': line.uom_id.id,
                                        'location_id': req.internal_picking_id.default_location_src_id.id,
                                        'location_dest_id': req.internal_picking_id.default_location_dest_id.id,
                                        'picking_id': stock_picking.id,
                                        'origin': req.sequence,
                                    }
                                    self.env['stock.move'].create(pic_line_val)
                    req.write({
                        'state': 'po_created',
                    })

    def action_approve(self):
        for req in self:
            req.write(
                {
                    'state': 'approved',
                    'approved_by_id': self.env.user.id,
                    'approved_date': datetime.now()
                }
            )

    def action_reject(self):
        for record in self:
            picking_requisition_ids = self.env['stock.picking'].search([('origin', '=', record.sequence)])
            if picking_requisition_ids:
                for req in picking_requisition_ids:
                    req.action_cancel()
                    req.unlink()
            pur_requisition_ids = self.env['purchase.order'].search([('origin', '=', record.sequence)])
            if pur_requisition_ids:
                for p_req in pur_requisition_ids:
                    p_req.button_cancel()
                    p_req.unlink()
            record.write({
                'state': 'cancel',
                'rejected_date': datetime.now(),
                'rejected_by_id': self.env.user.id
            })

    def reset_to_draft(self):
        for record in self:
            picking_requisition_ids = self.env['stock.picking'].search([('origin', '=', record.sequence)])
            if picking_requisition_ids:
                for rec in picking_requisition_ids:
                    rec.action_cancel()
                    rec.unlink()
            purchase_requisition_ids = self.env['purchase.order'].search([('origin', '=', record.sequence)])
            if purchase_requisition_ids:
                for rec in purchase_requisition_ids:
                    rec.button_cancel()
                    rec.unlink()
            record.write({
                'state': 'new'
            })

    def cancel_requisition(self):
        for record in self:
            picking_requisition_ids = self.env['stock.picking'].search([('origin', '=', record.sequence)])
            if picking_requisition_ids:
                for req in picking_requisition_ids:
                    req.action_cancel()
                    req.unlink()
            pur_requisition_ids = self.env['purchase.order'].search([('origin', '=', record.sequence)])
            if pur_requisition_ids:
                for p_req in pur_requisition_ids:
                    p_req.button_cancel()
                    p_req.unlink()
            record.write({
                'state': 'cancel'
            })

    def action_received(self):
        for record in self:
            record.write({
                'state': 'received',
                'rejected_date': datetime.now()
            })



    @api.onchange('department_id', 'employee_id')
    def onchange_department(self):
        for rec in self:
            rec.department_id = rec.employee_id.sudo().department_id.id


class RequisitionLine(models.Model):
    _name = 'requisition.line'

    _description = 'Requisition Line'
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Text('Description')
    qty = fields.Float('Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit Of Measure')
    requistion_id = fields.Many2one('minhduc.purchase.requisition', string="Requisition Line")
    vendor_id = fields.Many2many('res.partner', string='Vendors', required=True)
    requisition_action = fields.Selection(
        [
            ('purchase_order', 'Purchase Order'),
            ('internal_picking', 'Internal Picking')
        ], default='purchase_order', string='Requisition Action'
    )

    @api.onchange('product_id', 'description', 'uom_id')
    def onchange_product(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id.id
        return {}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    po_requisition_ids = fields.Many2one('minhduc.purchase.requisition', string='Purchase Requisition')


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    req_picking_id = fields.Many2one('minhduc.purchase.requisition', string='Purchase Requisition')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    destination_location_id = fields.Many2one('stock.location', 'Destination Location')


class HrDepartiment(models.Model):
    _inherit = 'hr.department'
    destination_location_id = fields.Many2one('stock.location', 'Destination Location')
