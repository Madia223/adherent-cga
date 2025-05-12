from odoo import models, fields, api
from datetime import timedelta, date

class FiscalEcheance(models.Model):
    _name = 'fiscal.echeance'
    _description = 'Échéance fiscale d’un adhérent'
    _order = 'deadline'

    name = fields.Char(string="Nom de l'impôt", required=True)
    partner_id = fields.Many2one('res.partner', string="Adhérent", required=True, ondelete='cascade')
    deadline = fields.Date(string="Échéance", required=True)
    regime_id = fields.Many2one('fiscal.regime', string="Régime Fiscal", required=True)
    taxe_id = fields.Many2one('fiscal.taxe', string="Taxe", required=True)

    state = fields.Selection([
        ('draft', 'À venir'),
        ('due', 'Échéance proche'),
        ('overdue', 'En retard'),
        ('paid', 'Payé'),
    ], string="Statut", default='draft', compute='_compute_state', store=True)

    paiement_effectue = fields.Boolean(string="Paiement effectué", default=False)
    payment_date = fields.Date(string="Date de paiement")

    @api.depends('deadline', 'paiement_effectue')
    def _compute_state(self):
        today = date.today()
        for record in self:
            if record.paiement_effectue:
                record.state = 'paid'
            elif record.deadline:
                if record.deadline < today:
                    record.state = 'overdue'
                elif (record.deadline - today).days <= 7:
                    record.state = 'due'
                else:
                    record.state = 'draft'
            else:
                record.state = 'draft'

    def action_marquer_comme_paye(self):
        """Action manuelle pour marquer une échéance comme payée"""
        for rec in self:
            rec.paiement_effectue = True
            rec.payment_date = fields.Date.today()

    @api.model
    def _cron_notify_upcoming_echeances(self):
        today = date.today()
        upcoming_date = today + timedelta(days=5)
        echeances = self.search([
            ('deadline', '>=', today),
            ('deadline', '<=', upcoming_date),
            ('paiement_effectue', '=', False),
        ])

        template = self.env.ref('adherent_cga.mail_template_fiscal_echeance_reminder')  # nom correct du template

        for echeance in echeances:
            if echeance.partner_id.email and template:
                # Envoie l’email via le template défini
                template.with_context(lang=echeance.partner_id.lang).send_mail(
                    echeance.id,
                    force_send=True,
                    email_values={
                        'email_to': echeance.partner_id.email,
                    }
                )
