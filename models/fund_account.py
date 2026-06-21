"""Fund account model used to track received funds, holds, and allocations.
Balances are computed from related ledger lines so the account reflects the
current unassigned balance, held amount, and total assigned amount.
"""

from odoo import models, fields, api

class FundAccount(models.Model):
    _name = 'nn.fund.account'
    _description = 'Fund Account'

    name = fields.Char(string="Account Name", required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    total_received = fields.Float(string="Total Received", compute="_compute_balances")
    unassigned_balance = fields.Float(string="Available Unassigned Balance", compute="_compute_balances")
    amount_held = fields.Float(string="Amount on Hold", compute="_compute_balances")
    total_assigned = fields.Float(string="Total Assigned Amount", compute="_compute_balances")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The account name must be unique!')
    ]

    def _compute_balances(self):
        for account in self:
            # Querying lines specific to this account
            lines = self.env['nn.fund.ledger'].search([('fund_account_id', '=', account.id)])
            
            received = sum(l.amount for l in lines if l.entry_type == 'unassigned')
            hold_alloc = sum(l.amount for l in lines if l.entry_type == 'hold_alloc')
            allocated = sum(l.amount for l in lines if l.entry_type == 'allocated')
            
            account.total_received = received
            account.unassigned_balance = received + hold_alloc - allocated
            account.amount_held = abs(hold_alloc)
            account.total_assigned = allocated