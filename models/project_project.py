"""Project extensions for tracking fund allocations and balances per project.
Adds computed fields that aggregate related fund ledger lines to present the
total allocated, available funds, holds, and spent amounts for a project.
"""

from odoo import models, fields

class Project(models.Model):
    _inherit = 'project.project'

    total_allocated = fields.Float(string="Total Allocated Fund", compute="_compute_fund_balances")
    available_fund = fields.Float(string="Available Fund", compute="_compute_fund_balances")
    requisition_hold = fields.Float(string="Requisition Hold", compute="_compute_fund_balances")
    transfer_hold = fields.Float(string="Transfer Hold", compute="_compute_fund_balances")
    spent_amount = fields.Float(string="Total Spent Amount", compute="_compute_fund_balances")

    def _compute_fund_balances(self):
        for rec in self:
            lines = self.env['nn.fund.ledger'].search([('project_id', '=', rec.id)])
            
            allocated = sum(l.amount for l in lines if l.entry_type == 'allocated')
            hold_req = sum(l.amount for l in lines if l.entry_type == 'hold_req')
            reserved = sum(l.amount for l in lines if l.entry_type == 'reserved')
            spent = sum(l.amount for l in lines if l.entry_type == 'spent')
            hold_trans = sum(l.amount for l in lines if l.entry_type == 'hold_trans')

            rec.total_allocated = allocated
            # Available is what was allocated minus what is held or spent
            rec.available_fund = allocated + hold_req + hold_trans - spent - reserved
            rec.requisition_hold = abs(hold_req)
            rec.transfer_hold = abs(hold_trans)
            rec.spent_amount = spent