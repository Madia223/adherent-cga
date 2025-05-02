# -*- coding: utf-8 -*-
# from odoo import http


# class Inovcga(http.Controller):
#     @http.route('/inovcga/inovcga', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/inovcga/inovcga/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('inovcga.listing', {
#             'root': '/inovcga/inovcga',
#             'objects': http.request.env['inovcga.inovcga'].search([]),
#         })

#     @http.route('/inovcga/inovcga/objects/<model("inovcga.inovcga"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('inovcga.object', {
#             'object': obj
#         })

