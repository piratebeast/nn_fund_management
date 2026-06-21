"""Expense head model for categorizing ledger entries by expense type.

This model stores the expense head name and serves as the lookup structure for
fund ledger allocations and reporting.
"""

from odoo import models, fields

class ExpenseHead(models.Model):
    _name = 'nn.expense.head'
    _description = 'Expense Head'

    name = fields.Char(string="Expense Head Name", required=True)
    
    # Structural balance fields computed from the ledger will be added here in Step 5