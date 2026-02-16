# models/adhesion_versement.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AdhesionVersement(models.Model):
    _name = 'adhesion.versement'
    _description = "Versement pour adhésion au CGA"
    _order = 'date_versement asc, id asc'

    name = fields.Char(
        "Référence", readonly=True, copy=False, default='Nouveau'
    )
    adherent_id = fields.Many2one(
        'res.partner', string="Adhérent",
        domain=[('is_adherent', '=', True)],
        required=True, ondelete='cascade',
    )
    montant = fields.Float("Montant versé", required=True)
    date_versement = fields.Date(
        "Date de versement", required=True, default=fields.Date.today
    )
    note = fields.Text("Observation")

    # ---- Champs informatifs (lecture seule) ----
    montant_adhesion = fields.Float(
        related='adherent_id.montant_adhesion',
        string="Frais d'adhésion", readonly=True,
    )
    reste_apres = fields.Float(
        "Reste après ce versement",
        compute='_compute_reste_apres', store=True,
    )

    # ---------------------------------------------------------
    #  Séquence automatique
    # ---------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('adhesion.versement.seq')
                    or 'Nouveau'
                )
        return super().create(vals_list)

    # ---------------------------------------------------------
    #  Calcul du reste après chaque versement
    # ---------------------------------------------------------
    @api.depends('montant', 'adherent_id.montant_adhesion',
                 'adherent_id.versement_adhesion_ids.montant',
                 'adherent_id.versement_adhesion_ids.date_versement')
    def _compute_reste_apres(self):
        for rec in self:
            if not rec.adherent_id:
                rec.reste_apres = 0
                continue
            # On trie tous les versements par date puis par id
            versements = rec.adherent_id.versement_adhesion_ids.sorted(
                key=lambda v: (v.date_versement or fields.Date.today(), v.id)
            )
            cumul = 0.0
            for v in versements:
                cumul += v.montant
                if v.id == rec.id:
                    break
            rec.reste_apres = rec.adherent_id.montant_adhesion - cumul

    # ---------------------------------------------------------
    #  Contraintes
    # ---------------------------------------------------------
    @api.constrains('montant')
    def _check_montant_positif(self):
        for rec in self:
            if rec.montant <= 0:
                raise ValidationError(
                    "Le montant du versement doit être strictement supérieur à 0."
                )

    @api.constrains('montant', 'adherent_id')
    def _check_pas_de_trop_verse(self):
        for rec in self:
            total = sum(rec.adherent_id.versement_adhesion_ids.mapped('montant'))
            plafond = rec.adherent_id.montant_adhesion
            if plafond and total > plafond:
                raise ValidationError(
                    "Le montant total versé (%.0f FCFA) dépasse les frais "
                    "d'adhésion (%.0f FCFA).\n"
                    "Trop-perçu : %.0f FCFA"
                    % (total, plafond, total - plafond)
                )