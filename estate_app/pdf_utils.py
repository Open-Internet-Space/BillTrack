"""
BillTrack - PDF Invoice Generator
SAFE + FIXED VERSION
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from io import BytesIO
from datetime import datetime


# ✅ SAFE FLOAT FUNCTION
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0


def generate_invoice_pdf(bill):
    from .models import SystemSettings
    from django.core.exceptions import ValidationError
    from xml.sax.saxutils import escape
    profile = SystemSettings.get_settings()
    if not profile.letterhead_name.strip():
        raise ValidationError('Configure the organisation name in Admin System Settings before printing invoices.')
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )

    elements = []
    styles = getSampleStyleSheet()

    # ── HEADER ─────────────────────────────────────────────
    elements.append(Paragraph("<b>" + escape(profile.letterhead_name) + "</b>", styles['Heading2']))
    elements.append(Paragraph(escape(profile.letterhead_department), styles['Normal']))
    elements.append(Paragraph("Monthly Billing Statement", styles['Normal']))
    elements.append(Spacer(1, 15))

    # ── INFO ───────────────────────────────────────────────
    invoice_display = bill.invoice_no if bill.invoice_no else "[Pending]"

    info_data = [
        ["Invoice No:", invoice_display, "Date:", datetime.now().strftime('%d-%b-%Y')],
        ["Period:", f"{bill.get_month_name()} {bill.year}", "Due Date:", bill.due_date.strftime('%d-%b-%Y')],
    ]

    info_table = Table(info_data, colWidths=[1.2*inch, 2*inch, 1*inch, 1.8*inch])
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # ── TENANT ─────────────────────────────────────────────
    tenant_data = [
        ["BILL TO"],
        [bill.tenant.name],
        [f"Contact: {'Not Provided' if bill.tenant.contact_not_provided else bill.tenant.contact}"],
    ]

    tenant_table = Table(tenant_data)
    tenant_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black)
    ]))

    elements.append(tenant_table)
    elements.append(Spacer(1, 15))

    # ── CHARGES ────────────────────────────────────────────
    charges_data = [
        ["Description", "Amount (₹)"],
        ["Rent (Base)", f"{safe_float(bill.rent):.2f}"],
    ]

    # GST
    if safe_float(bill.gst_on_rent) > 0:
        charges_data.append(["CGST @ 9%", f"{safe_float(bill.cgst_on_rent):.2f}"])
        charges_data.append(["SGST @ 9%", f"{safe_float(bill.sgst_on_rent):.2f}"])
        charges_data.append(["Rent (Including GST)", f"{safe_float(bill.rent_with_gst):.2f}"])

    # Other charges
    charges_data.extend([
        ["Electricity Charges", f"{safe_float(bill.electric):.2f}"],
        ["Water Charges", f"{safe_float(bill.water):.2f}"],
        ["", ""],
        ["TOTAL AMOUNT", f"{safe_float(bill.total_amount):.2f}"],
    ])

    # Payment info
    if safe_float(bill.amount_paid) > 0:
        charges_data.append(["Less: Paid", f"-{safe_float(bill.amount_paid):.2f}"])
        charges_data.append(["Balance", f"{safe_float(bill.balance_due):.2f}"])

    # Penalty
    if safe_float(bill.penalty) > 0:
        charges_data.append(["Penalty", f"{safe_float(bill.penalty):.2f}"])
        charges_data.append(["TOTAL PAYABLE", f"{safe_float(bill.total_payable):.2f}"])

    charges_table = Table(charges_data, colWidths=[4*inch, 2*inch])

    charges_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.black),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (1,-1), 'RIGHT'),
    ]))

    elements.append(charges_table)
    elements.append(Spacer(1, 20))

    # ── FOOTER ─────────────────────────────────────────────
    elements.append(Paragraph(
        "Payment terms and penalty/interest are applied as per the vendor billing profile.",
        styles['Normal']
    ))

    # BUILD
    doc.build(elements)
    buffer.seek(0)
    return buffer
