{
    'name': 'NN Fund Management',
    'version': '1.0',
    'category': 'Accounting/Finance',
    'summary': 'Manage incoming funds, allocations, requisitions, and transfers cleanly.',
    'author': 'Your Name',
    'company': 'NN Services & Engineering Ltd.',
    'depends': ['base', 'project'],  # Reusing native Odoo projects as planned
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/approval_decision_wizard_view.xml',
        'views/fund_account_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}