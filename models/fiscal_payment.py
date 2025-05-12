from odoo import models, fields, api
from datetime import date


class FiscalPayment(models.Model):
    _name = 'fiscal.payment'
    _description = 'Paiement fiscal d’un adhérent'
    _order = 'payment_date desc'

    name = fields.Char(string="Référence", required=True, default="/")
    partner_id = fields.Many2one('res.partner', string="Adhérent", required=True, ondelete='cascade')
    echeance_id = fields.Many2one('fiscal.echeance', string="Échéance concernée", required=True, ondelete='cascade')
    amount = fields.Float(string="Montant payé", required=True)
    payment_date = fields.Date(string="Date de paiement", default=fields.Date.context_today, required=True)
    notes = fields.Text(string="Notes")

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Payé'),
        ('cancel', 'Annulé'),
    ], string="Statut", default='draft')

    @api.model
    def create(self, vals):
        # Générer un nom automatique si nécessaire
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('fiscal.payment') or '/'
        return super().create(vals)

    @api.onchange('echeance_id')
    def _onchange_echeance_id(self):
        if self.echeance_id:
            self.partner_id = self.echeance_id.partner_id

    def action_mark_done(self):
        for payment in self:
            payment.state = 'done'
            if payment.echeance_id:
                payment.echeance_id.write({
                    'paiement_effectue': True,
                    'payment_date': payment.payment_date,
                })


    # def action_cancel(self):
    #     for payment in self:
    #         payment.state = 'cancel'
    #         if payment.echeance_id:
    #             payment.echeance_id.payment_status = 'late'

    def action_cancel(self):
        for payment in self:
            payment.state = 'cancel'
            if payment.echeance_id:
                payment.echeance_id.write({
                    'paiement_effectue': False,
                    'payment_date': False,
                })

