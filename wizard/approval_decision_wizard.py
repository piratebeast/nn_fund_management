from odoo import models, fields

class ApprovalDecisionWizard(models.Model):
    _name = 'nn.approval.decision.wizard'
    _description = 'Approval Decision Wizard'

    res_model = fields.Char(string="Model", required=True)
    res_id = fields.Integer(string="Record ID", required=True)

    action_type = fields.Selection([
        ('gm_approve', 'GM Approve'),
        ('md_approve', 'MD Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel')
    ], string="Action", required=True)

    comment = fields.Text(string="Remarks / Reason", required=True)

    def action_confirm(self):
        record = self.env[self.res_model].browse(self.res_id)
        
        if self.action_type == 'gm_approve':
            record.action_approve_gm(comment=self.comment)
        elif self.action_type == 'md_approve':
            record.action_approve_md(comment=self.comment)
        elif self.action_type == 'reject':
            record.action_reject(comment=self.comment)
        elif self.action_type == 'cancel':
            record.action_cancel(comment=self.comment)
        return {'type': 'ir.actions.act_window_close'}