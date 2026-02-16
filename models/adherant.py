import base64
import logging

import xlsxwriter
from dateutil.relativedelta import relativedelta
from openpyxl.workbook import Workbook
from datetime import datetime
from odoo import models, fields, api, _
from datetime import date
import io
from odoo.exceptions import UserError
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import base64
import os

from odoo.modules import get_module_resource

_logger = logging.getLogger(__name__)


class Adherant(models.Model):
    _inherit = 'res.partner'


    num_adh = fields.Char("numéro d'adhésion", readonly = True, compute = "_compute_num_adh")
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

    activity_type = fields.Char("Activité(s)", required=True)
    centre_des_impots = fields.Char("CDI", required=True)
    date_adhesion = fields.Date("Date d'adhésion", default=fields.Date.today(), required=True)
    montant_total = fields.Float("Montant total payé", compute='_compute_montant_total', store=True,
                                  readonly=True,
                                  help="Somme des paiements validés pour cet adhérent")


    # =============================================
    #   FRAIS D'ADHÉSION & VERSEMENTS
    # =============================================
    montant_adhesion = fields.Float(
        "Frais d'adhésion",
        default=0,
        help="Montant total à payer pour finaliser l'adhésion au CGA",
    )
    versement_adhesion_ids = fields.One2many(
        'adhesion.versement', 'adherent_id',
        string="Versements d'adhésion",
    )
    total_verse_adhesion = fields.Float(
        "Total versé (adhésion)",
        compute='_compute_adhesion_amounts',
        store=True, readonly=True,
    )
    reste_adhesion = fields.Float(
        "Reste à payer (adhésion)",
        compute='_compute_adhesion_amounts',
        store=True, readonly=True,
    )
    adhesion_soldee = fields.Boolean(
        "Adhésion soldée",
        compute='_compute_adhesion_amounts',
        store=True, readonly=True,
    )

    # =============================================
    #   COTISATIONS
    # =============================================
    cotisation_plan_ids = fields.One2many(
        'cotisation.plan', 'adherent_id',
        string="Plans de cotisation",
    )
    cotisation_count = fields.Integer(
        "Nb plans cotisation",
        compute='_compute_cotisation_count',
    )

    def _compute_cotisation_count(self):
        for rec in self:
            rec.cotisation_count = len(rec.cotisation_plan_ids)

    @api.depends('montant_adhesion', 'versement_adhesion_ids.montant')
    def _compute_adhesion_amounts(self):
        for rec in self:
            total = sum(rec.versement_adhesion_ids.mapped('montant'))
            rec.total_verse_adhesion = total
            rec.reste_adhesion = rec.montant_adhesion - total
            rec.adhesion_soldee = (
                rec.montant_adhesion > 0 and rec.reste_adhesion <= 0
            )


    @api.depends('raison_Sociale')
    def _compute_num_adh(self):
        for record in self:
            if record.raison_Sociale:
                record.num_adh = f"INOVCGAADH{record.raison_Sociale}{record.id}"
            else:
                record.num_adh = ""

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

            # Donne automatiquement accès au portail si email présent
            if adherent.email:
                portal_group = self.env.ref('base.group_portal')
                existing_user = self.env['res.users'].search([('partner_id', '=', adherent.id)], limit=1)

                if not existing_user:
                    user = self.env['res.users'].create({
                        'name': adherent.name,
                        'login': adherent.email,
                        'email': adherent.email,
                        'partner_id': adherent.id,
                        'groups_id': [(6, 0, [portal_group.id])],
                    })
                else:
                    user = existing_user
                    if portal_group not in existing_user.groups_id:
                        existing_user.groups_id = [(4, portal_group.id)]

                # Envoi automatique du lien d'activation portail (comme le bouton "réinitialiser mot de passe")
                try:
                    if user:
                        user.action_reset_password()
                        _logger.info(f"Lien de création de mot de passe envoyé à {adherent.email}")
                except Exception as e:
                    _logger.error(f"Erreur lors de l'envoi du lien d'accès portail à {adherent.email} : {e}")

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

    def get_portal_url(self):
        self.ensure_one()
        # Exemple d'URL vers le portail utilisateur Odoo standard
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/my"

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
            'ACTIVITES', 'MONTANT TOTAL', 'DGI'
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
    def print_adherent_status(self):
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from odoo.modules.module import get_module_resource
        import io, base64, os

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        logo_path = get_module_resource('adherent-cga', 'static/img', 'images.jpeg')

        for adherent in self:
            # Logo
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=100, height=100)
                elements.append(logo)
                elements.append(Spacer(1, 12))

            # Infos adhérent
            infos = f"""
                <b>Raison sociale :</b> {adherent.raison_Sociale or ''}<br/>
                <b>NUI :</b> {adherent.identification_fiscale or ''}<br/>
                <b>Régime fiscal :</b> {adherent.regime_id.name or ''}<br/>
                <b>Activité :</b> {adherent.activity_type or ''}<br/>
                <b>CDI :</b> {adherent.centre_des_impots or ''}<br/>
                <b>Date d'adhésion :</b> {adherent.date_adhesion or ''}<br/>
                <b>Montant total payé :</b> {adherent.montant_total:.2f} FCFA
            """
            styles = getSampleStyleSheet()
            custom_style = ParagraphStyle(
                name='CustomParagraph',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                leading=24  # C'est l'interligne
            )
            elements.append(Paragraph(f"<b>SITUATION DE : {adherent.raison_Sociale}</b>", styles['Title']))
            elements.append(Spacer(1, 50))
            elements.append(Paragraph(infos, custom_style))

            elements.append(Spacer(1, 25))

            # Tableau échéances
            data = [['Nom Échéance', 'État']]
            for e in adherent.echeance_ids:
                data.append([e.obligation.name, e.state])

            table = Table(data, colWidths=[250, 150], rowHeights=[30] * len(data))
            violet = colors.HexColor('#6A1B9A')
            orange = colors.HexColor('#FF9800')

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), violet),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
                ('GRID', (0, 0), (-1, -1), 1, orange),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))

            elements.append(table)
            elements.append(PageBreak())

        # Génération PDF
        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()

        # Enregistrement temporaire
        pdf_b64 = base64.b64encode(pdf_content)

        attachment = self.env['ir.attachment'].create({
            'name': 'statuts_adherents.pdf',
            'type': 'binary',
            'datas': pdf_b64,
            'res_model': 'adherent.cga',
            'res_id': self[0].id,
            'mimetype': 'application/pdf',
        })

        # Lien de téléchargement
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }

    def generate_carte_adhesion(self):
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        import io, base64, os
        from odoo.modules.module import get_module_resource

        self.ensure_one()
        buffer = io.BytesIO()
        width = 86 * mm
        height = 54 * mm
        doc = SimpleDocTemplate(buffer, pagesize=(width, height), leftMargin=5, rightMargin=5, topMargin=5,
                                bottomMargin=5)

        styles = getSampleStyleSheet()
        violet = colors.HexColor('#6A1B9A')
        orange = colors.HexColor('#FF9800')

        style_card = ParagraphStyle(
            name='CardStyle',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=colors.white,
            alignment=1,  # centre
            spaceAfter=3,
        )

        # Logo
        logo_path = get_module_resource('adherent-cga', 'static/img', 'images.jpeg')

        elements = []
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=30, height=30)
            elements.append(logo)

        # Bandeau violet
        elements.append(Spacer(1, 2))
        elements.append(Paragraph("CARTE D'ADHÉSION CGA", ParagraphStyle(
            name='TitleCard',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=orange,
            alignment=1
        )))

        # Tableau des infos
        data = [
            ['Nom / Raison sociale', self.raison_Sociale or ''],
            ['Numéro CGA', self.num_adh or ''],
            ['NUI', self.identification_fiscale or ''],
            ['Régime Fiscal', self.regime_id.name or ''],
            ['CDI', self.centre_des_impots or ''],
            ['Date d\'adhésion', self.date_adhesion.strftime('%d/%m/%Y') if self.date_adhesion else '']
        ]

        table = Table(data, colWidths=[40 * mm, 40 * mm], rowHeights=[5 * mm] * len(data))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), violet),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        elements.append(table)

        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()

        # Enregistrement
        pdf_b64 = base64.b64encode(pdf_content)
        attachment = self.env['ir.attachment'].create({
            'name': f"Carte_Adhésion_{self.name}.pdf",
            'type': 'binary',
            'datas': pdf_b64,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
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


    def portal_print_fiche(self):
        import io, base64, os
        from odoo.modules.module import get_module_resource
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        import logging

        _logger = logging.getLogger(__name__)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        adherent = self
        logo_path = get_module_resource('adherent-cga', 'static/img', 'images.jpeg')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=100, height=100)
            elements.append(logo)
            elements.append(Spacer(1, 12))

        infos = f"""
            <b>Raison sociale :</b> {adherent.raison_Sociale or ''}<br/>
            <b>NUI :</b> {adherent.identification_fiscale or ''}<br/>
            <b>Régime fiscal :</b> {adherent.regime_id.name or ''}<br/>
            <b>Activité :</b> {adherent.activity_type or ''}<br/>
            <b>CDI :</b> {adherent.centre_des_impots or ''}<br/>
            <b>Date d'adhésion :</b> {adherent.date_adhesion or ''}<br/>
            <b>Montant total payé :</b> {adherent.montant_total:.2f} FCFA
        """
        custom_style = ParagraphStyle(
            name='CustomParagraph',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=24
        )
        elements.append(Paragraph(f"<b>SITUATION DE : {adherent.raison_Sociale}</b>", styles['Title']))
        elements.append(Spacer(1, 50))
        elements.append(Paragraph(infos, custom_style))

        # Tableau des échéances
        data = [['Nom Échéance', 'État']]
        for e in adherent.echeance_ids:
            data.append([e.obligation.name, e.state])

        table = Table(data, colWidths=[250, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6A1B9A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#FF9800')),
        ]))
        elements.append(table)

        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()

        pdf_b64 = base64.b64encode(pdf_content)

        attachment = self.env['ir.attachment'].create({
            'name': 'fiche_adherent.pdf',
            'type': 'binary',
            'datas': pdf_b64,
            'res_model': 'res.partner',
            'res_id': self.id,
            'mimetype': 'application/pdf',
            'public': True  #  rend l'attachment accessible à tous les utilisateurs connectés
        })

        _logger.info("Attachment créé : ID=%s", attachment.id)

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }


class Echeance(models.Model):
    _name = "echeance"
    _description = "Échéance fiscale"

    name = fields.Char(string="Référence", readonly=True, compute="_compute_name", store=True)
    adherent_id = fields.Many2one("res.partner", string="Nom de l'adhérent", domain=[('is_adherent', '=', True)],
                                  ondelete='cascade')
    regime_id = fields.Many2one(related="adherent_id.regime_id", string="Régime Fiscal", readonly=True, store=True,
                                ondelete='cascade')
    obligation = fields.Many2one("fiscal.taxe", string="Obligation à payer", required=True,
                                 domain="[('regime_id', '=', regime_id)]", ondelete='cascade')
    state = fields.Selection([
        ('to_pay', 'À payer'),
        ('paid', 'Payé'),
        ('late', 'En retard')
    ], default='to_pay', readonly=True, string="Etat")
    date_echeance = fields.Date("Date d'échéance", compute="_compute_date_echeance", store=True)
    days_late = fields.Integer("Jours de retard", compute='_compute_days_late', store=True)
    paiement_ids = fields.One2many('paiement', 'echeance_id', string="Paiements")

    # ══════════════════════════════════════════════════════
    #   NOUVEAUX CHAMPS POUR LE SUIVI DES MONTANTS
    # ══════════════════════════════════════════════════════
    montant_attendu = fields.Float(
        "Montant attendu",
        default=0,
        help="Montant total à payer pour cette échéance fiscale",
    )
    total_verse = fields.Float(
        "Total versé",
        compute='_compute_total_verse',
        store=True,
        readonly=True,
    )
    reste_a_payer = fields.Float(
        "Reste à payer",
        compute='_compute_total_verse',
        store=True,
        readonly=True,
    )

    @api.depends('montant_attendu', 'paiement_ids.montant', 'paiement_ids.est_valide')
    def _compute_total_verse(self):
        for rec in self:
            total = sum(
                p.montant for p in rec.paiement_ids if p.est_valide
            )
            rec.total_verse = total
            rec.reste_a_payer = rec.montant_attendu - total

    @api.depends('adherent_id', 'obligation')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.adherent_id.name} - {record.obligation.name}"

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
    

   