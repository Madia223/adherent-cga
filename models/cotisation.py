# models/cotisation.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class CotisationPlan(models.Model):
    _name = 'cotisation.plan'
    _description = "Plan de cotisation adhérent CGA"
    _order = 'date_debut desc, id desc'

    name = fields.Char("Référence", readonly=True, copy=False, default='Nouveau')
    adherent_id = fields.Many2one(
        'res.partner', string="Adhérent",
        domain=[('is_adherent', '=', True)],
        required=True, ondelete='cascade',
    )
    montant_total = fields.Float("Montant total cotisation", required=True)
    nb_tranches = fields.Integer("Nombre de tranches", required=True, default=1)
    date_debut = fields.Date("Date de début", required=True, default=fields.Date.today)
    frequence = fields.Selection([
        ('mensuel', 'Mensuelle'),
        ('bimestriel', 'Bimestrielle (tous les 2 mois)'),
        ('trimestriel', 'Trimestrielle'),
        ('semestriel', 'Semestrielle'),
        ('annuel', 'Annuelle'),
        ('personnalise', 'Personnalisée'),
    ], string="Fréquence de paiement", required=True, default='mensuel')
    intervalle_jours = fields.Integer(
        "Intervalle (jours)",
        default=30,
        help="Utilisé uniquement si la fréquence est 'Personnalisée'",
    )

    tranche_ids = fields.One2many('cotisation.tranche', 'plan_id', string="Tranches")

    # Champs calculés
    total_verse = fields.Float(
        "Total versé", compute='_compute_totaux', store=True
    )
    reste_global = fields.Float(
        "Reste à payer", compute='_compute_totaux', store=True
    )
    nb_tranches_payees = fields.Integer(
        "Tranches payées", compute='_compute_totaux', store=True
    )
    progression = fields.Float(
        "Progression (%)", compute='_compute_totaux', store=True
    )

    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours', 'En cours'),
        ('solde', 'Soldé'),
        ('annule', 'Annulé'),
    ], default='brouillon', string="État", tracking=True)

    note = fields.Text("Observations")

    # ─── Séquence ───
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('cotisation.plan.seq')
                    or 'Nouveau'
                )
        return super().create(vals_list)

    # ─── Calculs ───
    @api.depends(
        'montant_total',
        'tranche_ids.montant_verse',
        'tranche_ids.state',
    )
    def _compute_totaux(self):
        for plan in self:
            total = sum(plan.tranche_ids.mapped('montant_verse'))
            nb_payees = len(plan.tranche_ids.filtered(lambda t: t.state == 'payee'))
            plan.total_verse = total
            plan.reste_global = plan.montant_total - total
            plan.nb_tranches_payees = nb_payees
            plan.progression = (
                (total / plan.montant_total * 100)
                if plan.montant_total else 0
            )

    # ─── Contraintes ───
    @api.constrains('montant_total')
    def _check_montant(self):
        for rec in self:
            if rec.montant_total <= 0:
                raise ValidationError("Le montant total doit être supérieur à 0.")

    @api.constrains('nb_tranches')
    def _check_nb_tranches(self):
        for rec in self:
            if rec.nb_tranches < 1:
                raise ValidationError("Le nombre de tranches doit être au minimum 1.")

    # ─── Calcul de l'intervalle selon fréquence ───
    def _get_relativedelta(self):
        self.ensure_one()
        mapping = {
            'mensuel': relativedelta(months=1),
            'bimestriel': relativedelta(months=2),
            'trimestriel': relativedelta(months=3),
            'semestriel': relativedelta(months=6),
            'annuel': relativedelta(years=1),
        }
        if self.frequence == 'personnalise':
            return relativedelta(days=self.intervalle_jours)
        return mapping.get(self.frequence, relativedelta(months=1))

    # ─── Générer les tranches ───
    def action_generer_tranches(self):
        for plan in self:
            if plan.state != 'brouillon':
                raise UserError("Les tranches ne peuvent être générées qu'en état brouillon.")

            if plan.tranche_ids:
                plan.tranche_ids.unlink()

            montant_tranche = round(plan.montant_total / plan.nb_tranches, 0)
            reste_repartition = plan.montant_total - (montant_tranche * plan.nb_tranches)
            delta = plan._get_relativedelta()

            tranches_vals = []
            for i in range(plan.nb_tranches):
                montant = montant_tranche
                # On ajoute le reste de la division à la dernière tranche
                if i == plan.nb_tranches - 1:
                    montant += reste_repartition

                date_prevue = plan.date_debut + (delta * i)

                tranches_vals.append({
                    'plan_id': plan.id,
                    'numero': i + 1,
                    'montant_prevu': montant,
                    'date_prevue': date_prevue,
                    'state': 'en_attente',
                })

            self.env['cotisation.tranche'].create(tranches_vals)
            plan.state = 'en_cours'

        return True

    # ─── Actions de workflow ───
    def action_remettre_brouillon(self):
        for plan in self:
            plan.tranche_ids.unlink()
            plan.state = 'brouillon'

    def action_annuler(self):
        for plan in self:
            plan.state = 'annule'

    def action_verifier_solde(self):
        """Appelé automatiquement ou manuellement pour vérifier si tout est payé"""
        for plan in self:
            if plan.reste_global <= 0 and plan.state == 'en_cours':
                plan.state = 'solde'


class CotisationTranche(models.Model):
    _name = 'cotisation.tranche'
    _description = "Tranche de cotisation"
    _order = 'numero asc'

    name = fields.Char("Libellé", compute='_compute_name', store=True)
    plan_id = fields.Many2one(
        'cotisation.plan', string="Plan de cotisation",
        required=True, ondelete='cascade',
    )
    adherent_id = fields.Many2one(
        related='plan_id.adherent_id', string="Adhérent",
        store=True, readonly=True,
    )
    numero = fields.Integer("N° Tranche", required=True)
    montant_prevu = fields.Float("Montant prévu", required=True)
    montant_verse = fields.Float("Montant versé", default=0)
    reste = fields.Float("Reste", compute='_compute_reste', store=True)
    date_prevue = fields.Date("Date prévue", required=True)
    date_paiement = fields.Date("Date de paiement effectif")

    state = fields.Selection([
        ('en_attente', 'En attente'),
        ('partiel', 'Partiellement payée'),
        ('payee', 'Payée'),
        ('en_retard', 'En retard'),
    ], default='en_attente', string="État")

    note = fields.Text("Observation")

    # ─── Nom automatique ───
    @api.depends('plan_id.name', 'numero')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.plan_id.name or ''} - Tranche {rec.numero}"

    # ─── Calcul du reste ───
    @api.depends('montant_prevu', 'montant_verse')
    def _compute_reste(self):
        for rec in self:
            rec.reste = rec.montant_prevu - rec.montant_verse

    # ─── Mise à jour du state quand on paie ───
    @api.onchange('montant_verse')
    def _onchange_montant_verse(self):
        for rec in self:
            if rec.montant_verse >= rec.montant_prevu:
                rec.state = 'payee'
                if not rec.date_paiement:
                    rec.date_paiement = fields.Date.today()
            elif rec.montant_verse > 0:
                rec.state = 'partiel'
            else:
                rec.state = 'en_attente'

    def write(self, vals):
        res = super().write(vals)
        if 'montant_verse' in vals:
            for rec in self:
                if rec.montant_verse >= rec.montant_prevu:
                    rec.state = 'payee'
                    if not rec.date_paiement:
                        rec.date_paiement = fields.Date.today()
                elif rec.montant_verse > 0:
                    rec.state = 'partiel'
                # Vérifier si le plan est soldé
                rec.plan_id.action_verifier_solde()
        return res

    # ─── Contraintes ───
    @api.constrains('montant_verse', 'montant_prevu')
    def _check_montant_verse(self):
        for rec in self:
            if rec.montant_verse < 0:
                raise ValidationError("Le montant versé ne peut pas être négatif.")
            if rec.montant_verse > rec.montant_prevu:
                raise ValidationError(
                    "Le montant versé (%.0f) dépasse le montant prévu (%.0f) "
                    "pour la tranche %d."
                    % (rec.montant_verse, rec.montant_prevu, rec.numero)
                )

    # ─── Cron : vérifier les retards ───
    @api.model
    def check_tranches_en_retard(self):
        today = fields.Date.today()
        tranches_late = self.search([
            ('state', 'in', ['en_attente', 'partiel']),
            ('date_prevue', '<', today),
        ])
        if tranches_late:
            tranches_late.write({'state': 'en_retard'})
            _logger.info(
                "%d tranche(s) de cotisation marquée(s) en retard.", len(tranches_late)
            )
        return True