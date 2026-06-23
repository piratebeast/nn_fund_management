"""Expense Head model to categorize expenses and compute fund balances.
This model defines expense heads for categorizing fund allocations and expenses.
Computed fields aggregate related ledger entries to show total allocated, available, held, and spent amounts for each expense head.
"""

from odoo import models, fields, api

class ExpenseHead(models.Model):
    _name = 'nn.expense.head'
    _description = 'Expense Head'

    name = fields.Char(string="Expense Head Name", required=True)
    total_allocated = fields.Float(string="Total Allocated Fund", compute="_compute_fund_balances")
    available_fund = fields.Float(string="Available Fund", compute="_compute_fund_balances")
    requisition_hold = fields.Float(string="Requisition Hold", compute="_compute_fund_balances")
    transfer_hold = fields.Float(string="Transfer Hold", compute="_compute_fund_balances")
    spent_amount = fields.Float(string="Total Spent Amount", compute="_compute_fund_balances")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Expense Head name must be unique!')
    ]

    def _compute_fund_balances(self):
        for rec in self:
            lines = self.env['nn.fund.ledger'].search([('expense_head_id', '=', rec.id)])
            
            allocated = sum(l.amount for l in lines if l.entry_type == 'allocated')
            hold_req = sum(l.amount for l in lines if l.entry_type == 'hold_req')
            reserved = sum(l.amount for l in lines if l.entry_type == 'reserved')
            spent = sum(l.amount for l in lines if l.entry_type == 'spent')
            hold_trans = sum(l.amount for l in lines if l.entry_type == 'hold_trans')

            rec.total_allocated = allocated
            rec.available_fund = allocated + hold_req + hold_trans - spent - reserved
            rec.requisition_hold = abs(hold_req)
            rec.transfer_hold = abs(hold_trans)
            rec.spent_amount = spent