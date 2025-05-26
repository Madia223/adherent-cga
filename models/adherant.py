from datetime import timedelta, date
from email.policy import default
import logging
from dateutil.utils import today

_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

from odoo import models, fields, api
from odoo.cli.scaffold import template


class Adherant(models.Model):
    _inherit = 'res.partner'

    raison_Sociale = fields.Char(string='Raison Sociale', required=True)
    identification_fiscale = fields.Char(string='NUI', required=True)
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts liés au régime', compute='_compute_taxes',
                               readonly=True)
    deadline = fields.Date(string="Échéance", compute="_compute_deadline", readonly=True)
    is_adherent = fields.Boolean("Est un adhérent", default=False, required=True)
    echeance_ids = fields.One2many('echeance', 'adherent_id', string="Échéances")
    all_echeances_paid = fields.Boolean("Toutes les échéances payées", compute='_compute_all_echeances_paid',
                                        store=True)

    @api.depends('echeance_ids.state')
    def _compute_all_echeances_paid(self):
        for adherent in self:
            if adherent.is_adherent and adherent.echeance_ids:
                adherent.all_echeances_paid = all(
                    echeance.state == 'paid'
                    for echeance in adherent.echeance_ids
                )
            else:
                adherent.all_echeances_paid = False

    @api.depends('regime_id')
    def _compute_taxes(self):
        for rec in self:
            rec.taxe_ids = rec.regime_id.taxe_ids if rec.regime_id else False

    @api.depends('regime_id')
    def _compute_deadline(self):
        for rec in self:
            rec.deadline = rec.regime_id.taxe_ids and rec.regime_id.taxe_ids[0].deadline or False

    @api.model
    def create(self, vals):
        # Création de l'adhérent
        adherent = super(Adherant, self).create(vals)

        # Si c'est un adhérent et qu'un régime est défini, créer les échéances
        if vals.get('is_adherent') and vals.get('regime_id'):
            adherent._create_echeances()

        return adherent

    def write(self, vals):
        res = super(Adherant, self).write(vals)

        # Si is_adherent devient True ou si le régime est modifié
        if 'is_adherent' in vals or 'regime_id' in vals:
            for adherent in self:
                if adherent.is_adherent and adherent.regime_id:
                    # Supprimer les anciennes échéances
                    adherent.echeance_ids.unlink()
                    # Créer les nouvelles échéances
                    adherent._create_echeances()

        return res

    def _create_echeances(self):
        """Crée automatiquement les échéances pour les obligations fiscales de l'adhérent"""

        Echeance = self.env['echeance']

        for adherent in self:
            if adherent.is_adherent and adherent.regime_id:
                for taxe in adherent.regime_id.taxe_ids:
                    Echeance.create({
                        'adherent_id': adherent.id,
                        'regime_id': adherent.regime_id.id,
                        'obligation': taxe.id,
                        'state': 'to_pay',
                    })
        _logger.info(f"Échéances créées automatiquement pour l'adhérent {self.id}")


class Echeance(models.Model):
    _name = "echeance"
    _description = "Échéance fiscale"

    name = fields.Char(string="Nom", compute="_compute_name", store=True)
    adherent_id = fields.Many2one("res.partner", string="Nom de l'adhérent", domain=[('is_adherent', '=', True)])
    regime_id = fields.Many2one(related="adherent_id.regime_id", string="Régime Fiscal", readonly=True, store=True)
    obligation = fields.Many2one("fiscal.taxe", string="Obligation à payer", required=True,
                                 domain="[('regime_id', '=', regime_id)]")
    state = fields.Selection([
        ('to_pay', 'À payer'),
        ('paid', 'Payé'),
        ('late', 'En retard')
    ], default='to_pay', readonly=True, string="Etat")
    date_echeance = fields.Date("Date d'échéance", compute="_compute_date_echeance", store=True)
    days_late = fields.Integer("Jours de retard", compute='_compute_days_late', store=True)

    # filtrage des obligations en fonction de leur régime
    @api.onchange('adherent_id')
    def _onchange_adherent_id(self):
        if self.adherent_id:
            self.regime_id = self.adherent_id.regime_id
            return {
                'domain': {
                    'obligation': [('regime_id', '=', self.regime_id.id)]
                }
            }


    @api.depends('adherent_id.name', 'obligation.name')
    def _compute_name(self):
        for record in self:
            adherent_name = record.adherent_id.name or ''
            obligation_name = record.obligation.name or ''
            record.name = f"{adherent_name} - {obligation_name}"

    # Récupère les échéances du field deadline en fonction des types d'impôts
    @api.depends('obligation.deadline')
    def _compute_date_echeance(self):
        for rec in self:
            rec.date_echeance = rec.obligation.deadline if rec.obligation else False

    # Vérification et mise à jour de L'Etat en fonction de la date d'échéance
    def check_expired_echeance(self):
        _logger.info("=== DÉBUT check_expired_echeances ===")
        today = fields.Date.today()

        # 1. Trouver les échéances "À payer" qui sont maintenant expirées
        expired_echeances = self.search([
            ('state', '=', 'to_pay'),
            ('date_echeance', '<', today)
        ])
        _logger.info(f"Échéances expirées trouvées: {len(expired_echeances)}")

        # 2. Trouver les échnces "En retard" qui ont maintenant une date future
        late_but_future_echeances = self.search([
            ('state', '=', 'late'),
            ('date_echeance', '>=', today)
        ])
        _logger.info(f"Échéances en retard mais avec date future trouvées: {len(late_but_future_echeances)}")

        # 3. Mettre m jour les états
        if expired_echeances:
            expired_echeances.write({'state': 'late'})
        if late_but_future_echeances:
            late_but_future_echeances.write({'state': 'to_pay'})

        return True

    @api.depends('date_echeance', 'state')
    def _compute_days_late(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'late' and rec.date_echeance and rec.date_echeance < today:
                rec.days_late = (today - rec.date_echeance).days
            else:
                rec.days_late = 0

    @api.onchange('date_echeance')
    def _onchange_date_echeance(self):
        today = fields.date.today()
        for rec in self:
            if rec.date_echeance and rec.date_echeance >= today:  # (si la date d'échéance est définie et que la date d'échéance est supérieure ou égale à la date d'aujourd'hui)
                rec.state = 'to_pay'
                rec.days_late = 0

            elif rec.date_echeance and rec.date_echeance < today:  # (si la date d'échéance est définie et que la date d'échéance est inférieure à la date d'aujourd'hui)
                rec.state = 'late'
                rec.days_late = (today - rec.date_echeance).days

    # @api.constrains('date_echeance', 'state')
    # def _check_date_echeance(self):
    #     """Valide que:
    #     - Une échéance antérieure à aujourd'hui a l'état 'late'.
    #     - Une échéance future a l'état 'to_pay' ou 'paid'.
    #     """
    #     today = fields.date.today()
    #     for rec in self:
    #         if rec.date_echeance and rec.date_echeance < today and rec.state != 'late':
    #             raise ValidationError(
    #                 "Une échéance dépassée doit être en état 'En retard'."
    #                 f"Date: {rec.date_echeance}, État actuel: {rec.state}"
    #             )
    #         if rec.date_echeance and rec.date_echeance >= today and rec.state == 'late':
    #             raise ValidationError(
    #                 "Une échéance future ne peut pas être en état 'En retard'. "
    #                 f"Date: {rec.date_echeance}"
    #             )

# Pour la relance par mails en fonction des retards sur l'échéance
#     @api.model
#     def check_late_payments_and_send_reminders(self):
#         _logger.info("=== DÉBUT check_late_payments ===")
#         today = fields.Date.today()
#         late_echeance = self.search([
#             ('state', '=', 'late'),
#             ('date_echeance', '<', today)
#         ])
#         _logger.info(f"Échéances en retard trouvées: {len(late_echeance)}")
#
#         for echeance in late_echeance:
#             regime = echeance.obligation.regime_id
#             if regime:
#                 days_late = (today - echeance.date_echeance).days
#                 if days_late >= regime.reminder_days:
#                     _logger.info(f"Envoi relance pour échéance {echeance.id}")
#                     self.send_reminder(echeance)
#         return True
#
#
#     def send_reminder(self, echeance):
#         #Créer un message de relance
#         template = self.env.ref('GESTION CGA.email_template_late_payment')
#         template.send_mail(echeance.id, force_send=True)
#         # Vous pouvez aussi enregistrer un message dans le chatter
#         echeance.message_post(
#             body=f"Relance automatique envoyée pour un retard de {echeance.days_late} jours",
#             subject="Relance pour paiement en retard"
#         )


# @api.model
# def create(self, vals):
#     # Logique de validation ou d'autres traitements
#     return super(Adherant, self).create(vals)
