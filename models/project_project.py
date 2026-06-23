from odoo import models, fields

class Project(models.Model):
    _inherit = 'project.project'

    total_allocated = fields.Float(string="Total Allocated Fund", compute="_compute_fund_balances")
    incoming_transfers = fields.Float(string="Incoming Transfers", compute="_compute_fund_balances")
    outgoing_transfers = fields.Float(string="Outgoing Transfers", compute="_compute_fund_balances")
    approved_unspent = fields.Float(string="Approved But Unspent Amount", compute="_compute_fund_balances")
    available_fund = fields.Float(string="Available Fund", compute="_compute_fund_balances")
    requisition_hold = fields.Float(string="Requisition Hold", compute="_compute_fund_balances")
    transfer_hold = fields.Float(string="Transfer Hold", compute="_compute_fund_balances")
    spent_amount = fields.Float(string="Total Spent Amount", compute="_compute_fund_balances")

    def _compute_fund_balances(self):
        for rec in self:
            lines = self.env['nn.fund.ledger'].search([('project_id', '=', rec.id)])
            
            # Filter pure allocations vs transfer-driven changes using origin markers
            allocated = sum(l.amount for l in lines if l.entry_type == 'allocated' and l.res_model == 'nn.fund.allocation')
            inc_xfr = sum(l.amount for l in lines if l.entry_type == 'allocated' and l.res_model == 'nn.fund.transfer' and l.amount > 0)
            out_xfr = sum(abs(l.amount) for l in lines if l.entry_type == 'allocated' and l.res_model == 'nn.fund.transfer' and l.amount < 0)
            
            hold_req = sum(l.amount for l in lines if l.entry_type == 'hold_req')
            reserved = sum(l.amount for l in lines if l.entry_type == 'reserved')
            spent = sum(l.amount for l in lines if l.entry_type == 'spent')
            hold_trans = sum(l.amount for l in lines if l.entry_type == 'hold_trans')

            rec.total_allocated = allocated
            rec.incoming_transfers = inc_xfr
            rec.outgoing_transfers = out_xfr
            rec.spent_amount = spent
            
            # Double-Entry Layout Sync Formulas matching Section 5 constraints exactly
            net_pool = allocated + inc_xfr - out_xfr
            rec.available_fund = net_pool + hold_req + hold_trans - spent - reserved
            rec.approved_unspent = reserved
            rec.requisition_hold = abs(hold_req)
            rec.transfer_hold = abs(hold_trans)