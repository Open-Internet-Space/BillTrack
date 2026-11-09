"""Generate authenticator QR images locally with the existing ReportLab dependency."""
import base64
from urllib.parse import quote, urlencode

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib.colors import white


def authenticator_uri(secret, label):
    return 'otpauth://totp/' + quote('BillTrack:' + label, safe='') + '?' + urlencode({
        'secret': secret, 'issuer': 'BillTrack', 'algorithm': 'SHA1', 'digits': 6, 'period': 30,
    })


def qr_data_uri(secret, label):
    drawing = Drawing(240, 240)
    drawing.add(Rect(0, 0, 240, 240, fillColor=white, strokeColor=None))
    drawing.add(QrCodeWidget(authenticator_uri(secret, label), barWidth=240, barHeight=240, barBorder=4, barLevel='M'))
    svg = renderSVG.drawToString(drawing)
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')
