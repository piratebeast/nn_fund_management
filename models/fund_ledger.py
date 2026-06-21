"""Fund ledger entries for tracking fund balances, allocations, and origin records.
This model stores ledger movements linked to a fund account, project, and
expense head, along with the entry type, amount, and source document metadata.
"""

from odoo import models, fields

class FundLedger(models.Model):
    _name = 'nn.fund.ledger'
    _description = 'Fund Management Ledger'
    _order = 'id desc'  # Default sorting by most recent entries

    fund_account_id = fields.Many2one('nn.fund.account', string="Fund Account", ondelete='restrict')
    project_id = fields.Many2one('project.project', string="Project", ondelete='restrict')
    expense_head_id = fields.Many2one('nn.expense.head', string="Expense Head", ondelete='restrict')

    amount = fields.Float(string = "Amount", required = True)

    entry_type = fields.Selection([
        ('unassigned', 'Unassigned Balance'),
        ('hold_alloc', 'Allocation Hold'),
        ('allocated', 'Allocated Balance'),
        ('hold_req', 'Requisition Hold'),
        ('reserved', 'Reserved for Bills'),
        ('spent', 'Spent Balance'),
        ('hold_trans', 'Transfer Hold')
    ], string = "Entry Type", required = True)

    res_model = fields.Char(string="Origin Document Model")
    res_id = fields.Integer(string="Origin Document ID")
    description = fields.Text(string="Description")

