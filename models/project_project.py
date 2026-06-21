from odoo import models, fields

class Project(models.Model):
    _inherit = 'project.project'

    # Extends the core project layout to keep track of financial modules
    # Balances will match expense heads dynamically via Step 5