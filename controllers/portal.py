from odoo import http
from odoo.http import request
from datetime import date
import logging

from werkzeug.utils import redirect     # pour la redirection vers l’URL du PDF

_logger = logging.getLogger(__name__)

class CGAPortal(http.Controller):

    @http.route(['/my'], type='http', auth="user", website=True)
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
    
    # @http.route(['/my/adherent/<int:adherent_id>/card'], type='http', auth='user', website=True, methods=['GET'], csrf=False,)
    # def portal_download_membership_card(self, adherent_id, **kwargs):
    #     """
    #     Lien déclenché par le bouton « Télécharger ma fiche d’adhérent ».
    #     """
    #     adherent = request.env['res.partner'].sudo().browse(adherent_id)
    #     print(f"👋 Route appelée pour adhérent ID = {adherent_id}")

    #     # Vérification de sécurité : le partner demandé doit être le partner connecté
    #     if not adherent or adherent.id != request.env.user.partner_id.id:
    #         _logger.warning(
    #             "Tentative d'accès non autorisée à la fiche adhérent %s par l'utilisateur %s",
    #             adherent_id,
    #             request.uid,
    #         )
    #         return request.not_found()

    #     # Appel à la méthode de génération du PDF
    #     #
    #     action = adherent.portal_fiche()  # ← ta méthode qui crée le PDF
    #     download_url = action['url']  # ex. /web/content/<att_id>?download=true
    #     _logger.info(download_url)

    #     # Redirection vers le téléchargement
    #     return redirect(download_url, code=303)


    @http.route('/my/adherent/card', type='http', auth='user', website=True)
    def download_fiche_adherent_portail(self, **kw):
        # Récupérer le partenaire lié à l’utilisateur connecté
        adherent = request.env.user.partner_id

        if not adherent:
            return request.not_found()

        # Générer et renvoyer le lien vers la fiche
        try:
            action = adherent.portal_print_fiche()
            return redirect(action.get('url'), code=303)

        except Exception as e:
            _logger.exception("Erreur lors de la génération de la fiche adhérent : %s", str(e))
            return request.not_found()