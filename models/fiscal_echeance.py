from odoo import models, fields

class FiscalEcheance(models.Model):
    _name = 'fiscal.echeance'
    _description = 'Échéance fiscale d’un adhérent'

    name = fields.Char(string="Nom de l'impôt", required=True)
    partner_id = fields.Many2one('res.partner', string="Adhérent", required=True, ondelete='cascade')
    deadline = fields.Date(string="Échéance", required=True)
    regime_id = fields.Many2one('fiscal.regime', string="Régime Fiscal", required=True)
    taxe_id = fields.Many2one('fiscal.taxe', string="Taxe", required=True)