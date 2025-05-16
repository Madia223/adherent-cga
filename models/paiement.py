from odoo import models, fields, api
from datetime import date

class Paiement(models.Model):
    _name = "paiement"
    _description = "Suivi des paiements des adhérents"

    #Champs de base
    name = fields.Char("Référence", readonly=True, default=lambda self: self.env['ir.sequence'].
                       next_by_code('paiement.seq'))
    adherent_id = fields.Many2one('res.partner', string="Adhérent", domain=[('is_adherent', '=', True)], required=True)
    echeance_id = fields.Many2one('echeance', string="Échéance liée", required=True)
    montant = fields.Float("Montant payé", required=True)
    date_paiement = fields.Date("Date de paiement", default=fields.Date.today(), required=True)
    mode_paiement = fields.Selection("payment_mode", string="Mode de paiement", required=True)
    def payment_mode (self):
        return [
            ('espece', 'Espèces'),
            ('cheque', 'Chèque'),
            ('virement', 'Virement Bancaire'),
            ('mobile', 'Paiement mobile')
        ]

    #Contrôle de validité
    est_valide = fields.Boolean('Paiement validé', default=False)

    #Relation avec la taxe
    taxe_id = fields.Many2one(related='echeance_id.obligation', string='Taxe/Obligation', readonly=True)

    #Changement d'état automatique
    @api.model
    def create(self, vals):
        paiement = super(Paiement, self).create(vals)
        paiement.update_echeance_state()
        return paiement

    def write(self, vals):
        res = super(Paiement, self).write(vals)
        if 'est_valide' in vals:
            self.update_echeance_state()
        return res

    def update_echeance_state(self):
        for rec in self:
            if rec.est_valide:
                rec.echeance_id.state = 'paid'
            else:
                # Vérifie si l'échéance est dépassée
                if rec.echeance_id.date_echeance < date.today():
                    rec.echeance_id.state = 'late'


