from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FundAllocation(models.Model):
    _name = 'nn.fund.allocation'
    _inherit = 'nn.approval.mixin', 'mail.thread'
    _description = 'Fund Allocation Request'
    _order = 'id desc'
    _auto = True

    name = fields.Char(string="Request Number", required=True, copy=False, readonly=True, default=lambda self: 'NEW')
    fund_account_id = fields.Many2one('nn.fund.account', string="Fund Account", required=True, ondelete='restrict')
    project_id = fields.Many2one('project.project', string="Project Target", ondelete='restrict')
    expense_head_id = fields.Many2one('nn.expense.head', string="Expense Head Target", ondelete='restrict')

    amount = fields.Float(string="Requested Amount", required=True)
    purpose = fields.Text(string="Purpose/Justification", required=True)
    attachment = fields.Binary(string="Supporting Attachment")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.allocation') or 'ALC-00000'
        return super().create(vals_list)

    @api.constrains('project_id', 'expense_head_id')
    def _check_exclusivity(self):
        for record in self:
            if record.project_id and record.expense_head_id:
                raise ValidationError("Business Rule Violation: A transaction must use either a project or an expense head, not both.")
            if not record.project_id and not record.expense_head_id:
                raise ValidationError("Business Rule Violation: You must select either a destination Project or an Expense Head.")

    @api.constrains('amount')
    def _check_positive_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError("The requested allocation amount must be greater than zero.")

    def action_submit(self):
        self.ensure_one()
        if self.amount > self.fund_account_id.unassigned_balance:
            raise ValidationError(f"Overdraft Blocked: Requested amount ({self.amount}) exceeds available unassigned pool ({self.fund_account_id.unassigned_balance}).")

        self.env['nn.fund.ledger'].create({
            'fund_account_id': self.fund_account_id.id,
            'amount': -self.amount,
            'entry_type': 'hold_alloc',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Pending allocation lock for {self.project_id.name or self.expense_head_id.name}. Ref: {self.name}"
        })

        super(FundAllocation, self).action_submit()

    def _finalize_ledger_entries(self):
        self.ensure_one()
        self.env['nn.fund.ledger'].create({
            'fund_account_id': self.fund_account_id.id,
            'amount': self.amount,
            'entry_type': 'hold_alloc',
            'res_model': self._name,
            'res_id': self.id,
        })
        self.env['nn.fund.ledger'].create({
            'fund_account_id': self.fund_account_id.id,
            'project_id': self.project_id.id or False,
            'expense_head_id': self.expense_head_id.id or False,
            'amount': self.amount,
            'entry_type': 'allocated',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Finalized funding released to destination account. Ref: {self.name}"
        })

    def _reverse_held_ledger_entries(self):
        self.ensure_one()
        ledger_entries = self.env['nn.fund.ledger'].search([('res_model', '=', self._name), ('res_id', '=', self.id)])
        hold_sum = sum(line.amount for line in ledger_entries if line.entry_type == 'hold_alloc')

        if hold_sum != 0:
            self.env['nn.fund.ledger'].create({
                'fund_account_id': self.fund_account_id.id,
                'amount': abs(hold_sum),
                'entry_type': 'hold_alloc',
                'res_model': self._name,
                'res_id': self.id,
                'description': f"Rollback allocation hold. Request {self.name} was rejected/cancelled."
            })