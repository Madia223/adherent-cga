from odoo import models, fields, api

class FiscalRegime(models.Model):
    _name = 'fiscal.regime'
    _description = 'Régime Fiscal'

    name = fields.Char(string='Nom du Régime', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts')



    def Afficher_Echeances(self):
        regimes = self.search([])
        echeances = []

        for regime in regimes:
            for taxe in regime.taxe_ids:
                echeances.append({
                    'regime': regime.name,
                    'impot': taxe.name,
                    'echeance': taxe.deadline,
                })
        #Afficher dans la console
        print("==== Liste des echeances fiscales ====")
        for e in echeances:
            print(f"Régime: {e['regime']} | impôt: {e['impot']} | echeance: {e['echeance']}")
        return echeances


class FiscalTaxe(models.Model):
    _name = 'fiscal.taxe'
    _description = 'Impôt du Régime Fiscal'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nom de l\'Impôt', required=True)
    deadline = fields.Date(string='Échéance')
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)

    # methode pour recuperer toutes les echeances dans un tableau et les afficher dans la console
    @api.model
    def PrintHello(self):
        # Cette méthode est un exemple de méthode qui pourrait être appelée par une action server
        print("Hello from the FiscalRegime model!")
        return None

    def afficher_echeances_console(self):
        taxes = self.env['fiscal.taxe'].search([])
        print("Liste complète des échéances des impôts :")
        for taxe in taxes:
            print(f"- {taxe.name} : échéance le {taxe.deadline}")
        return None
