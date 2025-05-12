from odoo import models, fields, api
from datetime import datetime

class PortalNotification(models.Model):
    _name = 'portal.notification'
    _description = 'Notification d’échéance fiscale envoyée à un adhérent'
    _order = 'date_notification desc'

    name = fields.Char(string="Titre", required=True, default="Notification d’échéance fiscale")
    partner_id = fields.Many2one('res.partner', string="Adhérent", required=True, ondelete='cascade')
    echeance_id = fields.Many2one('fiscal.echeance', string="Échéance concernée", required=True)
    date_notification = fields.Datetime(string="Date de notification", default=lambda self: fields.Datetime.now(), required=True)
    
    notification_type = fields.Selection([
        ('email', 'Email'),
        ('alerte', 'Alerte Interne'),
    ], string="Type de notification", required=True, default='email')

    message = fields.Text(string="Message envoyé")

    @api.model
    def create(self, vals):
        """ Envoie automatique de l'email si notification de type email """
        record = super().create(vals)
        if record.notification_type == 'email':
            template = self.env.ref('adherent-cga.email_template_fiscal_notification', raise_if_not_found=False)
            if template:
                template.send_mail(record.id, force_send=True)
        return record
