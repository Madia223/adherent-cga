from odoo import models, fields, api

class Adherant(models.Model):
    _inherit = 'res.partner'


    raison_Sociale = fields.Char(string='Raison Sociale', required=True)
    identification_fiscale = fields.Char(string='NUI', required=True)
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts liés au régime', compute='_compute_taxes',
                               readonly=True)
    deadline = fields.Date(string="Échéance", compute="_compute_deadline", readonly=True)


    @api.depends('regime_id')
    def _compute_taxes(self):
        for rec in self:
            rec.taxe_ids = rec.regime_id.taxe_ids if rec.regime_id else False

    @api.depends('regime_id')
    def _compute_deadline(self):
        for rec in self:
            rec.deadline = rec.regime_id.taxe_ids and rec.regime_id.taxe_ids[0].deadline or False


    # @api.model
    # def create(self, vals):
    #     # Logique de validation ou d'autres traitements
    #     return super(Adherant, self).create(vals)