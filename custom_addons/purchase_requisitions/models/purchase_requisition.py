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
        ('new', 'New'),
        ('department_approval', 'Waiting Department Approval'),
        ('approve_ur', 'Waiting User Approved'),
        ('approved', 'Approved'),
        ('po_created', 'Purchase Order Created'),
        ('receive', 'Receive'),
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
    internal_picking_id = fields.Many2one('stock.picking.type', 'Internal picking type', required=True)

    # @api.onchange('company_id','picking_type_id','choose_manual_location')
    # def _checker(self):
    #     pass

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
                                        'picking_type_id': req.picking_type_id.id,
                                        'product_uom': line.uom_id.id,
                                        'location_id': req.source_location_id.id,
                                        'location_dest_id': req.destination_location_id.id
                                    }
                                else:
                                    picking_line = {
                                        'name': line.product_id.name,
                                        'product_id': line.product_id.id,
                                        'product_uom_qty': line.qty,
                                        'product_uom': line.uom_id.id,
                                        'picking_type_id': req.picking_type_id.id,
                                        'location_id': req.internal_picking_id.default_location_src_id.id,
                                        'location_dest_id': req.picking_type_id.default_location_dest_id.id
                                    }
                                self.env['stock.move'].create(picking_line)
                            else:
                                if req.choose_manual_location:
                                    vals = {
                                        'partner_id': vendor.id,
                                        'picking_type_id': req
                                    }
                                    pass

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
        pass

    def reset_to_draft(self):
        for req in self:
            req.write({
                'state': 'new'
            })

    def action_received(self):
        for req in self:
            req.write({
                'state': 'received',
                'rejected_date': datetime.now()
            })

    def cancel_requisition(self):
        for rec in self:
            rec.write({
                'state': 'cancel'
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
    vendor_id = fields.Many2many('res.partner', string='Vendors')
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
