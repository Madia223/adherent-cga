import base64
import logging

import xlsxwriter
from dateutil.relativedelta import relativedelta
from openpyxl.workbook import Workbook
from datetime import  datetime
from odoo import models, fields, api, _
from datetime import date
import io
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Adherant(models.Model):
    _inherit = 'res.partner'


    raison_Sociale = fields.Char(string='Sigles', required=True)
    identification_fiscale = fields.Char(string='NUI', required=True)
    regime_id = fields.Many2one('fiscal.regime', string='Régime Fiscal', required=True)
    taxe_ids = fields.One2many('fiscal.taxe', 'regime_id', string='Impôts liés au régime', compute='_compute_taxes',
                               readonly=True)
    deadline = fields.Date(string="Échéance", compute="_compute_deadline", readonly=True)

    current_month_deadlines = fields.One2many(
        'fiscal.taxe', string="Échéances du mois en cours", compute='_compute_current_month_deadlines'
    )
    is_adherent = fields.Boolean("Est un adhérent", default=False, required=True)
    echeance_ids = fields.One2many('echeance', 'adherent_id', string="Échéances")
    all_echeances_paid = fields.Boolean("Toutes les échéances payées", compute='_compute_all_echeances_paid',
                                        store=True)
    dgi = fields.Boolean("DGI", default=True)
    ref_paiement = fields.Integer("REF PAIEMENT")
    num_avis = fields.Char("N° Avis")
    type_document = fields.Selection([
        ('quittance', 'QUITTANCE'),
        ('accuse de paiement', 'ACCUSÉ DE PAIEMENT')
    ], string="Type Document", required=True)
    activity_type = fields.Char("Activité(s)", required=True)
    centre_des_impots = fields.Char("CDI", required=True)
    date_adhesion = fields.Date("Date d'adhésion", default=fields.Date.today(), required=True);
    montant_total = fields.Float("Montant total payé", compute='_compute_montant_total', store=True,
                                  readonly=True,
                                  help="Somme des paiements validés pour cet adhérent")


    @api.depends('echeance_ids.paiement_ids.montant', 'echeance_ids.paiement_ids.est_valide')
    def _compute_montant_total(self):
        for adherent in self:
            paiements_valides = self.env['paiement'].search([
                ('adherent_id', '=', adherent.id),
                ('est_valide', '=', True)
            ])
            adherent.montant_total = sum(paiement.montant for paiement in paiements_valides)

    @api.depends('echeance_ids.state')
    def _compute_all_echeances_paid(self):
        for adherent in self:
            if adherent.is_adherent and adherent.echeance_ids:
                adherent.all_echeances_paid = all(
                    echeance.state == 'paid'
                    for echeance in adherent.echeance_ids
                )
            else:
                adherent.all_echeances_paid = False

    @api.depends('regime_id')
    def _compute_taxes(self):
        for rec in self:
            rec.taxe_ids = rec.regime_id.taxe_ids if rec.regime_id else False

    @api.depends('regime_id')
    def _compute_deadline(self):
        for rec in self:
            rec.deadline = rec.regime_id.taxe_ids and rec.regime_id.taxe_ids[0].deadline or False

    @api.depends('regime_id')
    def _compute_current_month_deadlines(self):
        today = date.today()
        for rec in self:
            if rec.regime_id:
                # Filtrer les taxes dont la deadline est dans le mois en cours
                deadlines = rec.regime_id.taxe_ids.filtered(
                    lambda t: t.deadline and t.deadline.year == today.year and t.deadline.month == today.month)
                rec.current_month_deadlines = deadlines
            else:
                rec.current_month_deadlines = False

    @api.model
    def create(self, vals):
        # Création de l'adhérent
        adherent = super(Adherant, self).create(vals)

        # Si c'est un adhérent et qu'un régime est défini, créer les échéances
        if vals.get('is_adherent') and vals.get('regime_id'):
            adherent._create_echeances()

        return adherent

    def write(self, vals):
        res = super(Adherant, self).write(vals)

        # Si is_adherent devient True ou si le régime est modifié
        if 'is_adherent' in vals or 'regime_id' in vals:
            for adherent in self:
                if adherent.is_adherent and adherent.regime_id:
                    # Supprimer les anciennes échéances
                    adherent.echeance_ids.unlink()
                    # Créer les nouvelles échéances
                    adherent._create_echeances()

        return res

    def _create_echeances(self):
        """Crée automatiquement les échéances pour les obligations fiscales de l'adhérent"""

        Echeance = self.env['echeance']

        for adherent in self:
            if adherent.is_adherent and adherent.regime_id:
                for taxe in adherent.regime_id.taxe_ids:
                    Echeance.create({
                        'adherent_id': adherent.id,
                        'regime_id': adherent.regime_id.id,
                        'obligation': taxe.id,
                        'state': 'to_pay',
                    })
        _logger.info(f"Échéances créées automatiquement pour l'adhérent {self.id}")

    # @api.model
    # def create(self, vals):
    #     # Logique de validation ou d'autres traitements
    #     return super(Adherant, self).create(vals)


    def export_adherent_excel(self):
        if not self:
            raise UserError(_("Veuillez selectionnez au moins 1 adhérent pour exporter"))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Defines styles
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#337ab7',
            'font_color': 'white',
            'border': 1,
            'font_size': 12
        })

        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'bottom': 2
        })

        regular_format = workbook.add_format({
            'border': 1,
            'text_wrap': True,
            'font_size': 10
        })

        # Create worksheet
        worksheet = workbook.add_worksheet('Contribuables SYNAPEC')

        # Write title
        worksheet.merge_range('A1:O1', 'FICHIER OFFICIEL DES CONTRIBUABLES SYNAPEC A PUBLIER', title_format)

        # Write headers
        headers = [
            'N°', 'NOM(S) ET PRENOM(S) ADHERENTS', 'SIGLES', 'DATES',
            'NIU', 'VILLES', 'TELEPHONES', 'CDI', 'REGIMES',
            'ACTIVITES', 'TYPE DOCUMENT', 'N° AVIS',
            'REF PAIEMENT', 'MONTANT TOTAL', 'DGI'
        ]

        for col, header in enumerate(headers):
            worksheet.write(1, col, header, header_format)

        # Write adherent data
        for row, adherent in enumerate(self.filtered(lambda r: r.is_adherent), 2):
            # Access both custom fields and native res.partner fields
            worksheet.write(row, 0, row - 1, regular_format)    # Nˆ
            worksheet.write(row, 1, adherent.name or '', regular_format)    # NOMS ET PRENOMS
            worksheet.write(row, 2, adherent.raison_Sociale or '', regular_format)   # Sigles
            worksheet.write(row, 3, adherent.date_adhesion.strftime('%Y-%m-%d') if adherent.date_adhesion else '', regular_format)  # Dates
            worksheet.write(row, 4, adherent.identification_fiscale or '', regular_format) # NIU
            worksheet.write(row, 5, adherent.city or '', regular_format)    # Villes
            worksheet.write(row, 6, adherent.phone or '', regular_format)   # Telephones
            worksheet.write(row, 7, adherent.centre_des_impots or '', regular_format)     # CDI
            worksheet.write(row, 8, adherent.regime_id.name if adherent.regime_id else '', regular_format)  # Regimes
            worksheet.write(row, 9, adherent.activity_type or '', regular_format)   # Activites
            worksheet.write(row, 10, adherent.type_document or '', regular_format)  # Type Document
            worksheet.write(row, 11, adherent.num_avis or '', regular_format) # N° AVIS
            worksheet.write(row, 12, adherent.ref_paiement or '', regular_format) # REF PAIEMENT
            worksheet.write(row, 13, adherent.montant_total or 0, regular_format) # montant total
            worksheet.write(row, 14, 'OUI' if adherent.dgi else 'NON', regular_format) # DGI (custom field)

        # Adjust column widths
        col_widths = {
            0: 5, 1: 30, 2: 15, 3: 12, 4: 20, 5: 15,
            6: 15, 7: 10, 8: 15, 9: 25, 10: 15, 11: 15,
            12: 20, 13: 15, 14: 15, 15: 10
        }

        for col, width in col_widths.items():
            worksheet.set_column(col, col, width)

        workbook.close()
        output.seek(0)

        # Return the Excel file as download
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=ir.attachment&field=datas&filename_field=name&id=%s' % self._create_excel_attachment(
                output).id,
            'target': 'self',
        }


    def _create_excel_attachment(self, file_data):
        """Create attachment record for the Excel file"""
        return self.env['ir.attachment'].create({
            'name': f"Contribuables_SYNAPEC_{datetime.now().strftime('%Y%m%d')}.xlsx",
            'type': 'binary',
            'datas': base64.b64encode(file_data.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': False,
        })


class Echeance(models.Model):
    _name = "echeance"
    _description = "Échéance fiscale"

    adherent_id = fields.Many2one("res.partner", string="Nom de l'adhérent", domain=[('is_adherent', '=', True)])
    regime_id = fields.Many2one(related="adherent_id.regime_id", string="Régime Fiscal", readonly=True, store=True)
    obligation = fields.Many2one("fiscal.taxe", string="Obligation à payer", required=True, domain="[('regime_id', '=', regime_id)]")
    state = fields.Selection([
        ('to_pay','À payer'),
        ('paid','Payé'),
        ('late', 'En retard')
    ], default='to_pay', readonly=True, string="Etat")
    date_echeance = fields.Date("Date d'échéance", compute="_compute_date_echeance", store=True)
    days_late = fields.Integer("Jours de retard", compute='_compute_days_late', store=True)
    paiement_ids = fields.One2many('paiement', 'echeance_id', string="Paiements")


#filtrage des obligations en fonction de leur régime
    @api.onchange('adherent_id')
    def _onchange_adherent_id(self):
        if self.adherent_id:
            self.regime_id = self.adherent_id.regime_id
            return {
                'domain': {
                    'obligation': [('regime_id', '=', self.regime_id.id)]
                }
            }


#Récupère les échéances du field deadline en fonction des types d'impôts
    @api.depends('obligation.deadline')
    def _compute_date_echeance(self):
        for rec in self:
            rec.date_echeance = rec.obligation.deadline if rec.obligation else False


#Vérification et mise à jour de L'Etat en fonction de la date d'échéance
    def check_expired_echeance(self):
        _logger.info("=== DÉBUT check_expired_echeances ===")
        today = fields.Date.today()

        # 1. Trouver les échéances "À payer" qui sont maintenant expirées
        expired_echeances = self.search([
            ('state', '=', 'to_pay'),
            ('date_echeance', '<', today)
        ])
        _logger.info(f"Échéances expirées trouvées: {len(expired_echeances)}")

        # 2. Trouver les échnces "En retard" qui ont maintenant une date future
        late_but_future_echeances = self.search([
            ('state', '=', 'late'),
            ('date_echeance', '>=', today)
        ])
        _logger.info(f"Échéances en retard mais avec date future trouvées: {len(late_but_future_echeances)}")

        # 3. Mettre m jour les états
        if expired_echeances:
            expired_echeances.write({'state': 'late'})
        if late_but_future_echeances:
            late_but_future_echeances.write({'state': 'to_pay'})

        return True


    @api.depends('date_echeance', 'state')
    def _compute_days_late(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'late' and rec.date_echeance and rec.date_echeance < today:
                rec.days_late = (today - rec.date_echeance).days
            else:
                rec.days_late = 0


    @api.onchange('date_echeance')
    def _onchange_date_echeance(self):
        today = fields.date.today()
        for rec in self:
            if rec.date_echeance and rec.date_echeance >= today: # (si la date d'échéance est définie et que la date d'échéance est supérieure ou égale à la date d'aujourd'hui)
                rec.state = 'to_pay'
                rec.days_late = 0

            elif rec.date_echeance and rec.date_echeance < today: # (si la date d'échéance est définie et que la date d'échéance est inférieure à la date d'aujourd'hui)
                rec.state = 'late'
                rec.days_late = (today - rec.date_echeance).days

    def _get_customer_information(self):
        self.ensure_one()
        if not self.adherent_id or not self.adherent_id.email:
            return {}
        return {
            'email': self.adherent_id.email,
            'name': self.adherent_id.name,
        }

    @api.model
    def send_monthly_echeance_reminders(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (first_day + relativedelta(months=1)) - relativedelta(days=1)

        echeances = self.search([
            ('date_echeance', '>=', today),
            ('date_echeance', '<=', last_day),
            ('state', '=', 'to_pay'),
            ('adherent_id.email', '!=', False),
        ])

        _logger.info(f"Envoi des rappels pour {len(echeances)} échéances à venir ce mois.")

        for echeance in echeances:
            if not echeance.adherent_id.is_adherent:
                _logger.info(f"Client {echeance.adherent_id.name} ignoré : ce n'est pas un adhérent.")
                continue  # Ne pas envoyer de mail si ce n'est pas un adhérent

            try:
                template = self.env.ref('adherent-cga.mail_template_adherent_cga')
                template.send_mail(echeance.id, force_send=True)
                _logger.info(f"Email envoyé à {echeance.adherent_id.name} ({echeance.adherent_id.email})")
            except Exception as e:
                _logger.error(f"Erreur lors de l'envoi du mail à {echeance.adherent_id.name}: {e}")

        return True

    @api.model
    def send_late_mail(self):
        today = fields.Date.today()

        # 1. S'assurer que les échéances sont bien marquées en 'late'
        self.check_expired_echeance()

        # 2. Récupérer les échéances en retard avec email valide
        echeances = self.search([
            ('state', '=', 'late'),
            ('date_echeance', '<', today),
            ('adherent_id.email', '!=', False),
        ])

        _logger.info(f"Traitement de {len(echeances)} échéances en retard")

        for echeance in echeances:
            adherent = echeance.adherent_id

            if not adherent.is_adherent:
                _logger.info(f"Client ignoré (non adhérent) : {adherent.name}")
                continue

            try:
                template = self.env.ref('adherent-cga.late_mail_template_adherent_cga')
                if template:
                    template.send_mail(echeance.id, force_send=True)
                    _logger.info(
                        f"Email de retard envoyé à {adherent.name} ({adherent.email}) - Échéance : {echeance.date_echeance}"
                    )
            except Exception as e:
                _logger.error(f"Erreur lors de l’envoi à {adherent.name} : {e}")

        return True
