from odoo import models, fields

class FiscalRegime(models.Model):
    _name = 'fiscal.regime'
    _description = 'Régime Fiscal'

    name = fields.Char(string='Nom du Régime', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts')


class FiscalTaxe(models.Model):
    _name = 'fiscal.taxe'
    _description = 'Impôt du Régime Fiscal'

    name = fields.Char(string='Nom de l\'Impôt', required=True)
    deadline = fields.Date(string='Échéance')
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)
