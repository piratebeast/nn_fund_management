"""Incoming fund transactions that create unassigned ledger entries.
This model stores incoming fund details, validates the amount, and confirms
transactions by posting them into the central fund ledger.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FundAccountTransaction(models.Model):
    _name = 'nn.fund.account.transaction'
    _description = 'Incoming Fund Transaction'
    _order = 'date desc, id desc'

    fund_account_id = fields.Many2one('nn.fund.account', string="Fund Account", required=True, ondelete='restrict')
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    amount = fields.Float(string="Amount", required=True)
    name = fields.Char(string="Transaction Reference", required=True)
    sender = fields.Char(string="Sender / Source", required=True)
    description = fields.Text(string="Description")
    attachment = fields.Binary(string="Attachment")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string="Status", default='draft', required=True, readonly=True)

    _sql_constraints = [
        ('ref_account_unique', 'unique(name, fund_account_id)', 'The transaction reference must be unique per fund account!')
    ]

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError("Transaction amount must be strictly greater than zero.")

    def action_confirm(self):
        """Confirms the transaction and posts it to the central ledger."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError("Only draft transactions can be confirmed.")

        # Write directly to the unified ledger system
        self.env['nn.fund.ledger'].sudo().create({
            'fund_account_id': self.fund_account_id.id,
            'amount': self.amount,
            'entry_type': 'unassigned',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Incoming fund from {self.sender}. Ref: {self.name}"
        })

        self.write({'state': 'confirmed'})