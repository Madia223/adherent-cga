# __manifest__.py
{
    'name': "GESTION CGA",

    'summary': "Module Odoo intégrant la gestion des obligations fiscales, "
               "la publication des échéances et le suivi des paiements.",

    'description': """
        • Automatiser l'enregistrement des adhérents et le paramétrage de leur régime fiscal.
        • Générer et publier les échéanciers fiscaux adaptés à chaque régime.
        • Programmer des notifications de rappel avant les échéances.
        • Assurer le suivi des paiements des obligations et alerter en cas de retard.
        • Suivre les versements d'adhésion au CGA.
    """,

    'author': "INOV CAMEROON",
    'website': "https://www.inov.cm",
    'category': 'Human Resources',
    'version': '1.1',

    'depends': ['base', 'calendar', 'portal', 'sale_subscription'],

     'data': [
        'security/ir.model.access.csv',
        'data/paiement_data.xml',
        'data/adhesion_data.xml',
        'data/cotisation_data.xml',              # ← NOUVEAU
        'data/fiscal_data.xml',
        'data/email_template.xml',
        'data/cron_data.xml',
        'views/views.xml',
        'views/adherent.xml',
        'views/echeance.xml',
        'views/paiement_view.xml',
        'views/fiscal_view.xml',
        'views/adhesion_versement_view.xml',
        'views/cotisation_view.xml',             # ← NOUVEAU
        'views/templates.xml',
        'views/portal_templates.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'adherent-cga/static/src/css/custom_portal.css',
        ],
    },                                           # ← FERMETURE CORRIGÉE

    'demo': [
        'demo/demo.xml',
    ],

    'application': True,
    'installable': True,
    'auto_install': False,
}