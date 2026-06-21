"""
Reusable approval workflow mixin and approval history log model.
The mixin provides state transitions, access checks, and approval history
logging for models that need a shared multi-step approval process.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ApprovalHistory(models.Model):
    _name = 'nn.approval.history'
    _description = 'Approval History Log'
    _order = 'id desc'

    res_model = fields.Char(string="Resource Model", required=True, index=True)
    res_id = fields.Integer(string="Resource ID", required=True, index=True)
    approver_id = fields.Many2one('res.users', string="Approver/Action Take by", default=lambda self: self.env.user)

    date = fields.Datetime(string="Action Date", default=fields.Datetime.now)

    approval_level = fields.Selection([
        ('submit', 'Submission'),
        ('gm', 'General Manager'),
        ('md', 'Managing Director'),
        ('reject', 'Rejection'),
        ('cancel', 'Cancellation')
    ], string="Action Level", required=True)

    result = fields.Selection([
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string="Result", required=True)

    comment = fields.Text(string="Comments/Remarks")


class ApprovalMixin(models.AbstractModel):
    _name = 'nn.approval.mixin'
    _description = 'Reusable Approval Workflow Mixin'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approval', 'GM Approval Pending'),
        ('md_approval', 'MD Approval Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', readonly=True) # tracking=True is removed for testing 

    requested_by = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user, readonly=True)
    request_date = fields.Date(string="Request Date", default=fields.Date.context_today, readonly=True)
    
    approval_history_ids = fields.One2many(
        'nn.approval.history', 
        compute='_compute_approval_history', 
        string="Approval / Action History"
    )

    def _compute_approval_history(self):
        for record in self:
            record.approval_history_ids = self.env['nn.approval.history'].search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id)
            ])

    def _log_approval(self, level, result, comment=False):
        self.env['nn.approval.history'].create({
            'res_model': self._name,
            'res_id': self.id,
            'approver_id': self.env.user.id,
            'approval_level': level,
            'result': result,
            'comment': comment
        })

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError("Only draft records can be submitted.")
            record._log_approval('submit', 'submitted')
            record.write({'state': 'submitted'})
            # Auto-route straight to GM approval phase
            record.action_route_to_gm()

    def action_route_to_gm(self):
        self.write({'state': 'gm_approval'})

    def action_approve_gm(self, comment=False):
        self.ensure_one()
        if self.state != 'gm_approval':
            raise ValidationError("Record is not awaiting GM approval.")
        if not self.env.user.has_group('nn_fund_management.group_gm_approver'):
            raise ValidationError("Only designated GM Approvers can execute this action.")
        if self.requested_by == self.env.user:
            raise ValidationError("Security Violation: You cannot approve your own request.")

        self._log_approval('gm', 'approved', comment)
        self.write({'state': 'md_approval'})

    def action_approve_md(self, comment=False):
        self.ensure_one()
        if self.state != 'md_approval':
            raise ValidationError("Record is not awaiting MD approval.")
        if not self.env.user.has_group('nn_fund_management.group_md_approver'):
            raise ValidationError("Only designated MD Approvers can execute this action.")
        if self.requested_by == self.env.user:
            raise ValidationError("Security Violation: You cannot approve your own request.")

        self._log_approval('md', 'approved', comment)
        self.write({'state': 'approved'})
        if hasattr(self, '_finalize_ledger_entries'):
            self._finalize_ledger_entries()

    def action_reject(self, comment=False):
        self.ensure_one()
        if self.state not in ['gm_approval', 'md_approval']:
            raise ValidationError("Can only reject records currently in an approval track.")
        
        # Enforce current role execution validation
        if self.state == 'gm_approval' and not self.env.user.has_group('nn_fund_management.group_gm_approver'):
            raise ValidationError("Only a GM Approver can reject this right now.")
        if self.state == 'md_approval' and not self.env.user.has_group('nn_fund_management.group_md_approver'):
            raise ValidationError("Only an MD Approver can reject this right now.")

        self._log_approval('reject', 'rejected', comment)
        self.write({'state': 'rejected'})
        if hasattr(self, '_reverse_held_ledger_entries'):
            self._reverse_held_ledger_entries()

    def action_cancel(self, comment=False):
        self.ensure_one()
        if self.state == 'approved' and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
            raise ValidationError("Only a Fund Administrator can cancel an already approved record.")
        if self.state in ['rejected', 'cancelled']:
            raise ValidationError("This record is already finalized.")

        self._log_approval('cancel', 'cancelled', comment)
        self.write({'state': 'cancelled'})
        if hasattr(self, '_reverse_held_ledger_entries'):
            self._reverse_held_ledger_entries()