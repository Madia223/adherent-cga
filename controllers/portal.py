# adherent-cga/controllers/portal.py
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class CGAPortal(CustomerPortal):

    @http.route(['/my/fiscal-echeances'], type='http', auth='user', website=True)
    def portal_my_fiscal_echeances(self, **kw):
        partner = request.env.user.partner_id
        echeances = request.env['fiscal.echeance'].sudo().search([
            ('partner_id', '=', partner.id)
        ])
        return request.render("adherent-cga.portal_my_fiscal_echeances", {
            'fiscal_echeances': echeances,
        })

    @http.route(['/my/fiscal-paiements'], type='http', auth='user', website=True)
    def portal_my_fiscal_payments(self, **kw):
        partner = request.env.user.partner_id
        payments = request.env['paiement.fiscal'].sudo().search([
            ('partner_id', '=', partner.id)
        ])
        return request.render("adherent-cga.portal_my_fiscal_payments", {
            'fiscal_payments': payments,
        })
