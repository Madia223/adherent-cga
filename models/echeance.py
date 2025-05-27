# from odoo import models, fields, api
# from odoo.exceptions import UserError
# from datetime import date, timedelta

# class Echeance(models.Model):
#     _name = 'echeance'
#     _description = 'Échéance Fiscale'

#     name = fields.Char()
#     date_echeance = fields.Date()
#     obligation_id = fields.Many2one('fiscal.taxe', string="Impôt")
#     adherent_id = fields.Many2one('res.partner', string="Adhérent")
#     paye = fields.Boolean(string="Payé", default=False)

#     def est_en_retard(self):
#         return not self.paye and self.date_echeance < date.today()

#     @api.model
#     def check_expired_echeance(self):
#         echeances = self.search([
#             ('paye', '=', False),
#             ('date_echeance', '<=', date.today() + timedelta(days=2))
#         ])
#         for echeance in echeances:
#             if echeance.adherent_id.email:
#                 template = request.env.ref('adherent-cga.mail_template_relance')
#                 request.env['mail.template'].browse(template.id).send_mail(echeance.id, force_send=True)
