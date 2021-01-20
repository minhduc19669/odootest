{
    'name': "Purchase Requisitions",
    'version': "13.0.0.1",
    'summary': 'Product Purchase Requisition for employee/user',
    'category': 'Purchases',
    'description': "Product Purchase Requisition",
    'author': "minhduc",
    'website': "minhduc.info",
    'depends': ['base','hr','purchase','stock','purchase_stock','sale_stock','sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'security/purchase_requisition_security.xml',
        'views/purchase_requisition_views.xml',
        'data/purchase_sequence.xml'
    ],
    'demo': [],
    'images': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
