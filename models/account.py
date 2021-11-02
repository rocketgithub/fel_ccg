# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

from datetime import datetime
import base64
from lxml import etree
import requests

import html
import uuid

import logging

class AccountMove(models.Model):
    _inherit = "account.move"

    pdf_fel = fields.Char('PDF FEL', copy=False)
    #name_pdf_fel = fields.Char('Nombre archivo PDF FEL', default='fel.pdf', size=32)
    
    def _post(self, soft=True):
        if self.certificar():
            return super(AccountMove, self)._post(soft)
        
    def post(self):
        if self.certificar():
            return super(AccountMove, self).post()

    def certificar(self):
        for factura in self:
            if factura.requiere_certificacion():
                self.ensure_one()
                
                if factura.error_pre_validacion():
                    return
                
                dte = factura.dte_documento()
                xmls = etree.tostring(dte, encoding="UTF-8")
                logging.warn(xmls)
                xmls_base64 = base64.b64encode(xmls)

                request_url = "https://ws.ccgfel.gt"
                if factura.company_id.pruebas_fel:
                    request_url = "https://testws.ccgfel.gt"
                    
                params = { "username": factura.company_id.usuario_fel, "password": factura.company_id.clave_fel, "grant_type": "password"}
                r = requests.post(request_url+"/Api/GetToken", data=params)
                logging.warn(r.text)
                resultado = r.json()

                if resultado["access_token"]:
                    token = resultado["access_token"]
                    referencia = factura.journal_id.code+str(factura.id)

                    headers = { "Authorization": "Bearer "+token }
                    params = { "xmlDte": xmls_base64, "Referencia": referencia }
                    r = requests.post(request_url+"/Api/CertificarDte", json=params, headers=headers)
                    logging.warn(r.text)
                    resultado = r.json()

                    if resultado["Resultado"]:
                        factura.firma_fel = resultado["UUID"]
                        factura.serie_fel = resultado["Serie"]
                        factura.numero_fel = resultado["Numero"]
                        factura.documento_xml_fel = xmls_base64
                        factura.resultado_xml_fel = resultado["XmlDteCertificado"]
                        factura.certificador_fel = "ccg"
                    else:
                        factura.error_certificador(r.text)
                        return False
                        
                else:
                    factura.error_certificador(r.text)
                    return False

        return True
    
    def button_cancel(self):
        result = super(AccountMove, self).button_cancel()
        for factura in self:
            if factura.requiere_certificacion() and factura.firma_fel:
                dte = factura.dte_anulacion()
                xmls = etree.tostring(dte, encoding="UTF-8")
                logging.warn(xmls)
                xmls_base64 = base64.b64encode(xmls)

                request_url = "https://ws.ccgfel.gt"
                if factura.company_id.pruebas_fel:
                    request_url = "https://testws.ccgfel.gt"

                params = { "username": factura.company_id.usuario_fel, "password": factura.company_id.clave_fel, "grant_type": "password"}
                r = requests.post(request_url+"/Api/GetToken", data=params)
                logging.warn(r.text)
                resultado = r.json()

                if resultado["access_token"]:
                    token = resultado["access_token"]
                    referencia = factura.journal_id.code+str(factura.id)

                    headers = { "Authorization": "Bearer "+token }
                    params = { "xmlDte": xmls_base64 }
                    r = requests.post(request_url+"/Api/AnularDte", json=params, headers=headers)
                    logging.warn(r.text)
                    resultado = r.json()
                    
                    if not resultado["Resultado"]:
                        raise UserError(r.text)
                else:
                    raise UserError(r.text)
                    
        return result
                
class AccountJournal(models.Model):
    _inherit = "account.journal"

    generar_fel = fields.Boolean('Generar FEL',)

class ResCompany(models.Model):
    _inherit = "res.company"

    usuario_fel = fields.Char('Usuario FEL')
    clave_fel = fields.Char('Clave FEL')
    pruebas_fel = fields.Boolean('Modo de Pruebas FEL')
    
