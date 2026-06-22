from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FundRequisition(models.Model):
    _name = 'nn.fund.requisition'
    _inherit = 'nn.approval.mixin', 'mail.thread'
    _description = 'Fund Requisition Request'
    _order = 'id desc'

    name = fields.Char(string="Requisition Number", required=True, copy=False, readonly=True, default=lambda self: 'NEW')
    project_id = fields.Many2one('project.project', string="Project Source", ondelete='restrict')
    expense_head_id = fields.Many2one('nn.expense.head', string="Expense Head Source", ondelete='restrict')

    requested_amount = fields.Float(string="Requested Amount", required=True)
    remaining_billable_amount = fields.Float(string="Remaining Billable Amount", compute="_compute_remaining_billable", store=True)

    purpose = fields.Text(string="Purpose/Justification", required=True)
    required_date = fields.Date(string="Required Date", required=True, default=fields.Date.context_today)
    attachment = fields.Binary(string="Supporting Attachment")
    attachment_filename = fields.Char(string="Attachment Filename")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    # NOTE: 'requested_by', 'request_date', 'state', 'approval_history_ids' and all
    # action_submit/approve_gm/approve_md/reject/cancel/_log_approval methods come
    # from nn.approval.mixin. Do not redefine them here.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.requisition') or 'REQ-00000'
        return super().create(vals_list)

    @api.constrains('project_id', 'expense_head_id')
    def _check_exclusivity(self):
        for record in self:
            if record.project_id and record.expense_head_id:
                raise ValidationError("Business Rule Violation: A transaction must use either a project or an expense head, not both.")
            if not record.project_id and not record.expense_head_id:
                raise ValidationError("Business Rule Violation: You must select either a source Project or an Expense Head.")

    # ------------------------------------------------------------------
    # Mixin overrides — requisition-specific ledger behavior.
    # The mixin calls action_submit() for the draft->submitted->gm_approval
    # transition, and calls _finalize_ledger_entries()/_reverse_held_ledger_entries()
    # via hasattr() at the approve_md/reject/cancel steps respectively. We override
    # action_submit() to add the hold; the other two hooks are pure additions.
    # ------------------------------------------------------------------

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError("Only draft requisitions can be submitted.")

            available = record.project_id.available_fund if record.project_id else record.expense_head_id.available_fund
            target_name = record.project_id.name if record.project_id else record.expense_head_id.name

            if record.requested_amount > available:
                raise ValidationError(
                    f"Insufficient Funds: Requested amount ({record.requested_amount}) exceeds "
                    f"available allocated balance ({available}) for '{target_name}'."
                )

            record.env['nn.fund.ledger'].create({
                'project_id': record.project_id.id or False,
                'expense_head_id': record.expense_head_id.id or False,
                'amount': -record.requested_amount,
                'entry_type': 'hold_req',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Pending requisition hold for {target_name}. Ref: {record.name}",
            })

        # Defer to the mixin for the actual state transition + logging + GM routing.
        super().action_submit()

    def _finalize_ledger_entries(self):
        """Called by the mixin's action_approve_md once state is set to 'approved'.
        Releases the hold_req hold and converts it into a reserved entry."""
        self.ensure_one()
        target_name = self.project_id.name if self.project_id else self.expense_head_id.name

        self.env['nn.fund.ledger'].create({
            'project_id': self.project_id.id or False,
            'expense_head_id': self.expense_head_id.id or False,
            'amount': self.requested_amount,
            'entry_type': 'hold_req',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Release requisition hold on MD approval. Ref: {self.name}",
        })
        self.env['nn.fund.ledger'].create({
            'project_id': self.project_id.id or False,
            'expense_head_id': self.expense_head_id.id or False,
            'amount': self.requested_amount,
            'entry_type': 'reserved',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Approved fund reservation for incoming bills. Ref: {target_name} / {self.name}",
        })

    def _reverse_held_ledger_entries(self):
        """Called by the mixin's action_reject/action_cancel.

        Which ledger entry_type needs reversing depends on how far the requisition
        got before being rejected/cancelled:
          - gm_approval / md_approval (pre-MD-approval): only the hold_req hold exists.
          - approved (cancel only — reject can't happen from here): the hold_req was
            already released and converted to 'reserved' by _finalize_ledger_entries,
            so it's the 'reserved' entry that must be reversed, not hold_req.
        """
        self.ensure_one()
        entry_type_to_reverse = 'reserved' if self.state == 'approved' else 'hold_req'

        ledger_entries = self.env['nn.fund.ledger'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('entry_type', '=', entry_type_to_reverse),
        ])
        net = sum(line.amount for line in ledger_entries)
        if net:
            self.env['nn.fund.ledger'].create({
                'project_id': self.project_id.id or False,
                'expense_head_id': self.expense_head_id.id or False,
                'amount': -net,
                'entry_type': entry_type_to_reverse,
                'res_model': self._name,
                'res_id': self.id,
                'description': f"Rollback {entry_type_to_reverse}. Request {self.name} was rejected/cancelled.",
            })

    @api.depends('state', 'requested_amount')
    def _compute_remaining_billable(self):
        for record in self:
            if record.state != 'approved':
                record.remaining_billable_amount = 0.0
                continue
            # Note: This will dynamically subtract matching vendor bills once the Bill model exists (Step 8).
            record.remaining_billable_amount = record.requested_amount