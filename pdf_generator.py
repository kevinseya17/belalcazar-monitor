"""
Generador de Comprobantes de Egreso en PDF
Replica el formato oficial de Supermercado Belalcázar
"""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

def formatear_fecha(fecha_str):
    try:
        parts = fecha_str.split("-")
        m_idx = int(parts[1]) - 1
        return f"{parts[0]}-{MESES[m_idx]}-{parts[2]}"
    except Exception:
        return fecha_str

def format_currency(val):
    try:
        return f"${float(val):,.0f}".replace(",", ".")
    except Exception:
        return str(val)

def generar_pdf_comprobante(data: dict, filepath: str):
    emp = data.get("empresa", {})
    ter = data.get("tercero", {})
    ban = data.get("banco", {})
    doc = data.get("documento", {})
    detalle = data.get("detalle", [])

    doc_pdf = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle('Norm', fontName='Helvetica', fontSize=8, leading=10)
    style_bold = ParagraphStyle('Bold', fontName='Helvetica-Bold', fontSize=8, leading=10)
    style_title = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=12, leading=14, alignment=2)
    style_empresa = ParagraphStyle('Emp', fontName='Helvetica-Bold', fontSize=11, leading=13)

    elements = []

    # 1. ENCABEZADO
    empresa_info = f"<b>{emp.get('nombre', '')}</b><br/>NIT: {emp.get('nit', '')}-{emp.get('dv', '')}<br/>{emp.get('direccion', '')} - {emp.get('ciudad', '')}<br/>Tel: {emp.get('telefono', '')}"
    doc_info = f"<font color='#003366'><b>COMPROBANTE DE EGRESO</b></font><br/><b>Nro:</b> {doc.get('numero_completo', '')}<br/><b>Fecha:</b> {formatear_fecha(doc.get('fecha', ''))}"

    header_table = Table(
        [[Paragraph(empresa_info, style_normal), Paragraph(doc_info, style_title)]],
        colWidths=[340, 200]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    # 2. CUADRO INFORMACIÓN BENEFICIARIO
    valor_fmt = format_currency(doc.get('valor_pagado', 0))
    info_pago = [
        [
            Paragraph("<b>PAGADO A:</b>", style_normal),
            Paragraph(ter.get('nombre', ''), style_normal),
            Paragraph("<b>NIT/CC:</b>", style_normal),
            Paragraph(f"{ter.get('nit', '')}-{ter.get('dv', '')}", style_normal)
        ],
        [
            Paragraph("<b>DIRECCIÓN:</b>", style_normal),
            Paragraph(f"{ter.get('direccion', '')} ({ter.get('ciudad', '')})", style_normal),
            Paragraph("<b>VALOR:</b>", style_normal),
            Paragraph(f"<b><font size=10 color='#B22222'>{valor_fmt} COP</font></b>", style_normal)
        ],
        [
            Paragraph("<b>CONCEPTO:</b>", style_normal),
            Paragraph(doc.get('concepto', ''), style_normal),
            Paragraph("", style_normal),
            Paragraph("", style_normal)
        ]
    ]

    pago_table = Table(info_pago, colWidths=[70, 260, 50, 160])
    pago_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#EAEAEA")),
        ('SPAN', (1, 2), (3, 2)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(pago_table)
    elements.append(Spacer(1, 10))

    # 3. INFORMACIÓN BANCARIA
    elements.append(Paragraph("<b>INFORMACIÓN PARA CONSIGNACIÓN</b>", style_bold))
    elements.append(Spacer(1, 3))
    
    banco_info = [
        ["Banco", "Nro. Cuenta", "Tipo Cuenta", "Titular"],
        [
            ban.get("nombre", "N/A"),
            ban.get("cuenta", "N/A"),
            ban.get("tipo", "N/A"),
            ban.get("titular", "N/A")
        ]
    ]
    banco_table = Table(banco_info, colWidths=[130, 140, 100, 170])
    banco_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(banco_table)
    elements.append(Spacer(1, 10))

    # 4. CONTABILIZACIÓN
    elements.append(Paragraph("<b>CONTABILIZACIÓN Y CRUCE DE DOCUMENTOS</b>", style_bold))
    elements.append(Spacer(1, 3))

    det_rows = [["Cuenta", "C.O", "Tercero", "Dcto Cruce / Factura", "Débitos", "Créditos"]]
    tot_deb = 0
    tot_cred = 0
    for d in detalle:
        deb = float(d.get("debito", 0) or 0)
        cred = float(d.get("credito", 0) or 0)
        tot_deb += deb
        tot_cred += cred
        det_rows.append([
            d.get("cuenta", ""),
            d.get("centro_operativo", ""),
            d.get("tercero", ""),
            d.get("doc_cruce", ""),
            format_currency(deb) if deb > 0 else "",
            format_currency(cred) if cred > 0 else ""
        ])

    det_rows.append([
        "SUMAS IGUALES", "", "", "",
        format_currency(tot_deb or doc.get("total_debito", 0)),
        format_currency(tot_cred or doc.get("total_credito", 0))
    ])

    det_table = Table(det_rows, colWidths=[80, 40, 90, 150, 90, 90])
    det_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1F497D")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
        ('ALIGN', (0, 0), (3, -1), 'CENTER'),
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
        ('SPAN', (0, -1), (3, -1)),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F0F0F0")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(det_table)
    elements.append(Spacer(1, 25))

    # 5. FIRMAS
    firmas = [
        ["________________________", "________________________", "________________________"],
        ["Elaborado Por", "Revisado / Aprobado", "Firma y Sello Beneficiario (C.C/NIT)"]
    ]
    firmas_table = Table(firmas, colWidths=[180, 180, 180])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
    ]))
    elements.append(firmas_table)

    doc_pdf.build(elements)
    return filepath
