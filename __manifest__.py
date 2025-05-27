# -*- coding: utf-8 -*-
{
    'name': "GESTION CGA",

    'summary': "module Odoo intégrant la gestion des obligations fiscales, la publication des échéances et le suivi des paiements.",

    'description': """
            •	Automatiser l'enregistrement des adhérents et le paramétrage de leur régime fiscal.
            •	Générer et publier les échéanciers fiscaux adaptés à chaque régime.
            •	Programmer des notifications de rappel avant les échéances.
            •	Assurer le suivi des paiements des obligations et alerter en cas de retard.

    """,

    'author': "INOV CAMEROON",
    'website': "https://www.inov.cm",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'calendar', 'mail', 'portal', 'website', ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/adherant.xml',
        'views/fiscal_view.xml',
        'views/templates.xml',
        'views/paiement_views.xml',
        'data/paiement_data.xml',
        'data/fiscal_data.xml',
        'data/cron.xml',
        'data/action_server.xml',
        'data/action_server_calendar.xml',


        'data/mail_templates.xml',
        'views/portal_templates.xml',
    ],

    'qweb': [
    'static/src/xml/portal_templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application' : True,
    'installable' : True,
    'auto_install' : False
}

