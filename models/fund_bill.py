from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FundRequisition(models.Model):
    """Pragmatic model extension to cleanly connect Vendor Bills back to Requisitions."""
    _inherit = 'nn.fund.requisition'

    bill_ids = fields.One2many('nn.fund.bill', 'requisition_id', string="Vendor Bills")

    @api.depends('state', 'requested_amount', 'bill_ids.amount', 'bill_ids.state')
    def _compute_remaining_billable(self):
        """Dynamically tracks remaining balance by subtracting posted bills."""
        for record in self:
            if record.state != 'approved':
                record.remaining_billable_amount = 0.0
                continue
            posted_bills_sum = sum(bill.amount for bill in record.bill_ids if bill.state == 'posted')
            record.remaining_billable_amount = record.requested_amount - posted_bills_sum


class FundBill(models.Model):
    _name = 'nn.fund.bill'
    _inherit = ['mail.thread']
    _description = 'Fund Vendor Bill'
    _order = 'id desc'

    name = fields.Char(string="Bill Number", required=True, copy=False, readonly=True, default=lambda self: 'NEW')
    requisition_id = fields.Many2one(
        'nn.fund.requisition',
        string="Requisition Source",
        required=True,
        domain="[('state', '=', 'approved')]",
        ondelete='restrict'
    )

    project_id = fields.Many2one('project.project', string="Project", related="requisition_id.project_id", store=True, readonly=True)
    expense_head_id = fields.Many2one('nn.expense.head', string="Expense Head", related="requisition_id.expense_head_id", store=True, readonly=True)

    supplier_id = fields.Many2one('res.partner', string="Vendor / Supplier", required=True)
    bill_date = fields.Date(string="Bill Date", required=True, default=fields.Date.context_today)
    amount = fields.Float(string="Bill Amount", required=True)

    description = fields.Text(string="Remarks/Notes")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', readonly=True, tracking=True)

    @api.constrains('amount', 'requisition_id')
    def _check_bill_amount(self):
        """Fast-fail validation for obviously-bad input at save time.

        NOTE: this is a UX nicety only — it is NOT the authoritative double-spend
        guard, because remaining_billable_amount only reflects POSTED bills, so two
        concurrently-created drafts can both pass this check against the same
        budget. The real guard against double-spending lives in action_post(),
        which takes a row lock on the requisition before re-checking the amount.
        """
        for record in self:
            if record.state == 'draft':
                if record.amount <= 0:
                    raise ValidationError("Business Rule Violation: Bill amount must be greater than zero.")

                if record.amount > record.requisition_id.remaining_billable_amount:
                    raise ValidationError(
                        f"Over-billing Violation: Requested bill amount ({record.amount}) exceeds the "
                        f"remaining billable room ({record.requisition_id.remaining_billable_amount}) "
                        f"available on Requisition {record.requisition_id.name}."
                    )

    def action_post(self):
        """Finalizes bill details and executes ledger asset transitions.

        Ledger writes use .sudo() because regular Fund Users only have create
        access on nn.fund.bill, not on nn.fund.ledger directly (by design — we
        don't want any user able to fabricate arbitrary ledger rows). The actual
        authorization gate is the state check above and the row lock below, not
        the ir.model.access entry on nn.fund.ledger; sudo() here only elevates
        privilege for these specific, narrowly-scoped, code-controlled writes.
        """
        for record in self:
            if record.state != 'draft':
                raise ValidationError("Only draft bills can be posted to the general ledger.")

            # Lock the requisition row for the rest of this transaction.
            record.env.cr.execute(
                "SELECT id FROM nn_fund_requisition WHERE id = %s FOR UPDATE",
                (record.requisition_id.id,)
            )

            record.requisition_id.invalidate_recordset(['remaining_billable_amount'])
            remaining = record.requisition_id.remaining_billable_amount

            if record.amount > remaining:
                raise ValidationError(
                    f"Cannot post bill: Amount ({record.amount}) exceeds the remaining "
                    f"billable balance ({remaining}) on the requisition."
                )

            # Double-Entry Ledger Movement:
            # 1. Deduct the value from the 'reserved' holding bucket
            record.env['nn.fund.ledger'].sudo().create({
                'project_id': record.project_id.id or False,
                'expense_head_id': record.expense_head_id.id or False,
                'amount': -record.amount,
                'entry_type': 'reserved',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Drawdown reservation asset for Bill {record.name}",
            })

            # 2. Record the permanent actual cash expense outflow line
            record.env['nn.fund.ledger'].sudo().create({
                'project_id': record.project_id.id or False,
                'expense_head_id': record.expense_head_id.id or False,
                'amount': record.amount,
                'entry_type': 'spent',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Actual payout execution for Vendor Bill {record.name}",
            })

            record.write({'state': 'posted'})

    def action_cancel(self):
        """Gracefully re-allocates funds back to the reservation pool upon cancellation.

        Same .sudo() reasoning as action_post — see note there.
        """
        for record in self:
            if record.state != 'posted':
                raise ValidationError("Only posted invoices can be cancelled to trigger ledger adjustments.")

            record.env.cr.execute(
                "SELECT id FROM nn_fund_requisition WHERE id = %s FOR UPDATE",
                (record.requisition_id.id,)
            )

            # Perfect mathematical negation of the original post:
            record.env['nn.fund.ledger'].sudo().create({
                'project_id': record.project_id.id or False,
                'expense_head_id': record.expense_head_id.id or False,
                'amount': record.amount,
                'entry_type': 'reserved',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Re-reserve balance from cancelled Bill {record.name}",
            })
            record.env['nn.fund.ledger'].sudo().create({
                'project_id': record.project_id.id or False,
                'expense_head_id': record.expense_head_id.id or False,
                'amount': -record.amount,
                'entry_type': 'spent',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Reverse actual payout transaction rows for Bill {record.name}",
            })
            record.write({'state': 'cancelled'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.bill') or 'BILL-00000'
        return super().create(vals_list)