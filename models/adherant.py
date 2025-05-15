from odoo import models, fields, api
from datetime import date

class Adherant(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    identification_fiscale = fields.Char(string='NUI', required=True)
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts liés au régime', compute='_compute_taxes',
                               readonly=True)
    deadline = fields.Date(string="Échéance", compute="_compute_deadline", readonly=True)

    current_month_deadlines = fields.One2many(
        'fiscal.taxe', string="Échéances du mois en cours", compute='_compute_current_month_deadlines'
    )

    @api.depends('regime_id')
    def _compute_taxes(self):
        for rec in self:
            rec.taxe_ids = rec.regime_id.taxe_ids if rec.regime_id else False

    @api.depends('regime_id')
    def _compute_deadline(self):
        for rec in self:
            rec.deadline = rec.regime_id.taxe_ids and rec.regime_id.taxe_ids[0].deadline or False

    @api.depends('regime_id')
    def _compute_current_month_deadlines(self):
        today = date.today()
        for rec in self:
            if rec.regime_id:
                # Filtrer les taxes dont la deadline est dans le mois en cours
                deadlines = rec.regime_id.taxe_ids.filtered(
                    lambda t: t.deadline and t.deadline.year == today.year and t.deadline.month == today.month)
                rec.current_month_deadlines = deadlines
            else:
                rec.current_month_deadlines = False

    @api.model
    def send_adherent_mail(self):
        adherents = self.search([])
        template = self.env.ref('adherent-cga.mail_template_adherent_cga')
        if not template:
            raise ValueError("Le modèle d'email 'mail_template_adherent_cga' n'existe pas.")
        for adherent in adherents:
            template.send_mail(adherent.id, force_send=True)


    # @api.model
    # def create(self, vals):
    #     # Logique de validation ou d'autres traitements
    #     return super(Adherant, self).create(vals)