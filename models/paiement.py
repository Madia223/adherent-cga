# models/paiement.py

from odoo import models, fields, api
from datetime import date


class Paiement(models.Model):
    _name = "paiement"
    _description = "Suivi des paiements des adhérents"

    name = fields.Char("Référence", readonly=True, default=lambda self: self.env['ir.sequence'].
                       next_by_code('paiement.seq'))
    adherent_id = fields.Many2one('res.partner', string="Adhérent", domain=[('is_adherent', '=', True)], required=True)
    echeance_id = fields.Many2one('echeance', string="Échéance liée", required=True)
    montant = fields.Float("Montant payé", required=True)
    date_paiement = fields.Date("Date de paiement", default=fields.Date.today(), required=True)
    mode_paiement = fields.Selection([
        ('espece', 'Espèces'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement Bancaire'),
        ('mobile', 'Paiement mobile')
    ], string="Mode de paiement", required=True)
    quittance = fields.Binary("Quittance de paiement",
                              help="Joindre une quittance ou un justificatif de paiement", required=True)
    num_quittance = fields.Char("Numéro de quittance",
                                help="Numéro de la quittance ou du justificatif de paiement", required=True)

    est_valide = fields.Boolean('Paiement validé', default=False)
    taxe_id = fields.Many2one(related='echeance_id.obligation', string='Taxe/Obligation', readonly=True)

    @api.model
    def create(self, vals):
        paiement = super(Paiement, self).create(vals)
        paiement._update_echeance_state()
        paiement._check_all_echeances_paid()
        return paiement

    def write(self, vals):
        res = super(Paiement, self).write(vals)
        if 'est_valide' in vals or 'montant' in vals:
            self._update_echeance_state()
            self._check_all_echeances_paid()
        return res

    def _update_echeance_state(self):
        """Met à jour l'état de l'échéance selon le total versé"""
        for rec in self:
            echeance = rec.echeance_id
            if not echeance:
                continue

            # Total des paiements validés pour cette échéance
            total_verse = sum(
                p.montant for p in echeance.paiement_ids if p.est_valide
            )

            # Si pas de montant attendu défini, on considère payé dès qu'il y a un versement validé
            if echeance.montant_attendu <= 0:
                if total_verse > 0 and rec.est_valide:
                    echeance.state = 'paid'
                return

            # Calcul du reste
            reste = echeance.montant_attendu - total_verse

            if reste <= 0:
                echeance.state = 'paid'
            else:
                if echeance.date_echeance and echeance.date_echeance < date.today():
                    echeance.state = 'late'
                else:
                    echeance.state = 'to_pay'

    def _check_all_echeances_paid(self):
        """Vérifie si toutes les échéances de l'adhérent sont payées"""
        for rec in self:
            adherent = rec.adherent_id
            if adherent.is_adherent:
                echeances_non_payees = self.env['echeance'].search([
                    ('adherent_id', '=', adherent.id),
                    ('state', '!=', 'paid')
                ])
                adherent.all_echeances_paid = not echeances_non_payees