from odoo import models, fields, api

class Adherant(models.Model):
    _inherit = 'res.partner'


    raison_Sociale = fields.Char(string='Raison Sociale', required=True)
    identification_fiscale = fields.Char(string='NUI', required=True)
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)


    # @api.model
    # def create(self, vals):
    #     # Logique de validation ou d'autres traitements
    #     return super(Adherant, self).create(vals)