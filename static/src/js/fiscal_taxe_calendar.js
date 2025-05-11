odoo.define('votre_module.fiscal_taxe_calendar', function (require) {
    "use strict";

    var CalendarView = require('web.CalendarView');
    var rpc = require('web.rpc');

    CalendarView.include({
        init: function () {
            this._super.apply(this, arguments);
            // Appeler la méthode serveur au chargement de la vue calendrier
            rpc.query({
                route: '/fiscal_taxe/check_deadlines',
                params: {},
            }).then(function (result) {
                console.log('check_tax_deadlines executed:', result);
            });
        },
    });
});
