from odoo import http
from odoo.http import request
from datetime import date

class CGAPortal(http.Controller):

    @http.route(['/my/echeances'], type='http', auth="user", website=True)
    def portal_agenda_fiscal(self, **kwargs):
        # Récupérer le partenaire lié à l'utilisateur connecté
        adherent = request.env.user.partner_id

        # Debug : Afficher l'identifiant du partenaire utilisateur
        _logger = http.logging.getLogger(__name__)
        _logger.info("Utilisateur connecté : %s (partner_id=%s)", request.env.user.name, adherent.id)

        # Rechercher les échéances liées à ce partenaire
        echeances = request.env['echeance'].sudo().search([
            ('adherent_id', '=', adherent.id)
        ], order="date_echeance asc")

        _logger.info("Nombre d'échéances trouvées : %s", len(echeances))

        # Rendu de la page HTML du portail
        return request.render("adherent-cga.portal_echeance_page", {
            'echeances': echeances,
            'page_name': 'echeances',  # Utile pour activer l’onglet actif
        })
