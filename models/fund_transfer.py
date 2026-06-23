from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FundTransfer(models.Model):
    _name = 'nn.fund.transfer'
    _inherit = 'nn.approval.mixin', 'mail.thread'
    _description = 'Internal Transfer Between Projects/Expense Heads'
    _order = 'id desc'

    name = fields.Char(string="Transfer Reference", required=True, copy=False, readonly=True, default=lambda self: 'NEW')

    source_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string="Source Type", required=True, default='project')
    destination_type = fields.Selection([
        ('project', 'Project'),
        ('expense', 'Expense Head'),
    ], string="Destination Type", required=True, default='project')

    source_project_id = fields.Many2one('project.project', string="Source Project", ondelete='restrict')
    source_expense_head_id = fields.Many2one('nn.expense.head', string="Source Expense Head", ondelete='restrict')
    destination_project_id = fields.Many2one('project.project', string="Destination Project", ondelete='restrict')
    destination_expense_head_id = fields.Many2one('nn.expense.head', string="Destination Expense Head", ondelete='restrict')

    amount = fields.Float(string="Transfer Amount", required=True)
    transfer_date = fields.Date(string="Transfer Date", required=True, default=fields.Date.context_today)
    description = fields.Text(string="Reason / Remarks", required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    # NOTE: 'requested_by', 'request_date', 'state', 'approval_history_ids' and all
    # action_submit/approve_gm/approve_md/reject/cancel/_log_approval methods come
    # from nn.approval.mixin. Only action_submit is overridden below.

    @api.constrains('source_type', 'destination_type', 'source_project_id', 'source_expense_head_id',
                     'destination_project_id', 'destination_expense_head_id', 'amount')
    def _check_transfer_integrity(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError("Business Rule Violation: Transfer amount must be greater than zero.")

            if record.source_type == 'project' and not record.source_project_id:
                raise ValidationError("Please select a source project.")
            if record.source_type == 'expense' and not record.source_expense_head_id:
                raise ValidationError("Please select a source expense head.")
            if record.destination_type == 'project' and not record.destination_project_id:
                raise ValidationError("Please select a destination project.")
            if record.destination_type == 'expense' and not record.destination_expense_head_id:
                raise ValidationError("Please select a destination expense head.")

            src_id = record.source_project_id.id if record.source_type == 'project' else record.source_expense_head_id.id
            dest_id = record.destination_project_id.id if record.destination_type == 'project' else record.destination_expense_head_id.id
            if record.source_type == record.destination_type and src_id == dest_id:
                raise ValidationError("Business Rule Violation: Source and Destination cannot be the same.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('nn.fund.transfer') or 'XFR-00000'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Row locking helpers. Projects and expense heads live in different
    # tables, so we lock each table's relevant ids separately, but always
    # in (table_name, sorted ids) order so any two transfers touching an
    # overlapping set of rows always acquire locks in the same global
    # order and cannot deadlock against each other.
    # ------------------------------------------------------------------

    def _dimension_ids(self):
        """Returns (project_ids, expense_head_ids) touched by this transfer."""
        self.ensure_one()
        project_ids = []
        expense_ids = []
        if self.source_type == 'project':
            project_ids.append(self.source_project_id.id)
        else:
            expense_ids.append(self.source_expense_head_id.id)
        if self.destination_type == 'project':
            project_ids.append(self.destination_project_id.id)
        else:
            expense_ids.append(self.destination_expense_head_id.id)
        return sorted(set(project_ids)), sorted(set(expense_ids))

    def _lock_dimensions(self):
        """Locks the project.project and nn_expense_head rows involved in this
        transfer, always projects first then expense heads, both in sorted-id
        order, so concurrent transfers touching overlapping rows never deadlock."""
        self.ensure_one()
        project_ids, expense_ids = self._dimension_ids()
        if project_ids:
            self.env.cr.execute(
                "SELECT id FROM project_project WHERE id IN %s FOR UPDATE",
                (tuple(project_ids),)
            )
        if expense_ids:
            self.env.cr.execute(
                "SELECT id FROM nn_expense_head WHERE id IN %s FOR UPDATE",
                (tuple(expense_ids),)
            )

    def _source_dimension_vals(self):
        self.ensure_one()
        return {
            'project_id': self.source_project_id.id if self.source_type == 'project' else False,
            'expense_head_id': self.source_expense_head_id.id if self.source_type == 'expense' else False,
        }

    def _destination_dimension_vals(self):
        self.ensure_one()
        return {
            'project_id': self.destination_project_id.id if self.destination_type == 'project' else False,
            'expense_head_id': self.destination_expense_head_id.id if self.destination_type == 'expense' else False,
        }

    def _source_available(self):
        self.ensure_one()
        return self.source_project_id.available_fund if self.source_type == 'project' else self.source_expense_head_id.available_fund

    # ------------------------------------------------------------------
    # Mixin overrides — transfer-specific ledger behavior.
    # All nn.fund.ledger.create() calls below use .sudo() because regular
    # Fund Users only have create access on nn.fund.transfer, not on
    # nn.fund.ledger directly (by design — no user should be able to
    # fabricate arbitrary ledger rows). The real authorization gate is the
    # state/group checks in the mixin and the balance checks below, not the
    # ir.model.access entry on nn.fund.ledger itself.
    # ------------------------------------------------------------------

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError("Only draft transfers can be submitted.")

            record._lock_dimensions()

            # Force a fresh read now that we hold the lock.
            if record.source_type == 'project':
                record.source_project_id.invalidate_recordset(['available_fund'])
            else:
                record.source_expense_head_id.invalidate_recordset(['available_fund'])
            available = record._source_available()

            source_name = record.source_project_id.name if record.source_type == 'project' else record.source_expense_head_id.name
            if record.amount > available:
                raise ValidationError(
                    f"Insufficient Funds: Cannot place transfer hold for {record.amount}. "
                    f"Available balance on '{source_name}' is {available}."
                )

            record.env['nn.fund.ledger'].sudo().create({
                **record._source_dimension_vals(),
                'amount': -record.amount,
                'entry_type': 'hold_trans',
                'res_model': record._name,
                'res_id': record.id,
                'description': f"Pending transfer hold on '{source_name}'. Ref: {record.name}",
            })

        super().action_submit()

    def _finalize_ledger_entries(self):
        """Called by the mixin's action_approve_md once state is set to 'approved'.
        Releases the hold_trans hold and posts the real debit/credit movement
        as 'allocated' entries, matching the entry_type that project/expense-head
        balance computations already treat as the post-allocation pool."""
        self.ensure_one()
        self._lock_dimensions()

        source_vals = self._source_dimension_vals()
        dest_vals = self._destination_dimension_vals()

        # 1. Release the submission-time hold.
        self.env['nn.fund.ledger'].sudo().create({
            **source_vals,
            'amount': self.amount,
            'entry_type': 'hold_trans',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Release transfer hold on MD approval. Ref: {self.name}",
        })

        # 2. Debit source dimension.
        self.env['nn.fund.ledger'].sudo().create({
            **source_vals,
            'amount': -self.amount,
            'entry_type': 'allocated',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Transfer outflow. Ref: {self.name}",
        })

        # 3. Credit destination dimension.
        self.env['nn.fund.ledger'].sudo().create({
            **dest_vals,
            'amount': self.amount,
            'entry_type': 'allocated',
            'res_model': self._name,
            'res_id': self.id,
            'description': f"Transfer inflow. Ref: {self.name}",
        })

    def _reverse_held_ledger_entries(self):
        """Called by the mixin's action_reject/action_cancel.

        State-aware, search-and-negate — never a blind re-derivation from
        self.amount, and never abs() on a signed sum.

          - gm_approval / md_approval (pre-MD-approval): only the hold_trans
            hold on the source dimension exists. Reverse it.
          - approved (cancel only — reject can't happen from here): the hold
            was already released and 'allocated' entries were posted on both
            source and destination by _finalize_ledger_entries. Reverse those.
        """
        self.ensure_one()
        self._lock_dimensions()

        if self.state == 'approved':
            for dim_vals in (self._source_dimension_vals(), self._destination_dimension_vals()):
                domain = [
                    ('res_model', '=', self._name),
                    ('res_id', '=', self.id),
                    ('entry_type', '=', 'allocated'),
                ]
                if dim_vals['project_id']:
                    domain.append(('project_id', '=', dim_vals['project_id']))
                else:
                    domain.append(('expense_head_id', '=', dim_vals['expense_head_id']))

                entries = self.env['nn.fund.ledger'].search(domain)
                net = sum(line.amount for line in entries)
                if net:
                    self.env['nn.fund.ledger'].sudo().create({
                        **dim_vals,
                        'amount': -net,
                        'entry_type': 'allocated',
                        'res_model': self._name,
                        'res_id': self.id,
                        'description': f"REVERSAL: Cancelled transfer {self.name}",
                    })
        else:
            entries = self.env['nn.fund.ledger'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('entry_type', '=', 'hold_trans'),
            ])
            net = sum(line.amount for line in entries)
            if net:
                self.env['nn.fund.ledger'].sudo().create({
                    **self._source_dimension_vals(),
                    'amount': -net,
                    'entry_type': 'hold_trans',
                    'res_model': self._name,
                    'res_id': self.id,
                    'description': f"Rollback transfer hold. Transfer {self.name} was rejected/cancelled.",
                })
