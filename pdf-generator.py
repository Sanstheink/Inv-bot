from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

def create_document_pdf(title, content):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, title)
    c.setFont("Helvetica", 12)
    y = 780
    for line in content.split("\n"):
        c.drawString(50, y, line)
        y -= 20
    c.save()
    buffer.seek(0)
    return buffer

def create_invoice_pdf(customer, items, vat=False):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 800, "ใบกำกับภาษี / Invoice")
    c.setFont("Helvetica", 12)
    c.drawString(50, 780, f"ลูกค้า / Customer: {customer}")

    y = 750
    total = 0
    for item in items:
        name = item['name']
        qty = item['qty']
        price = item['price']
        c.drawString(50, y, f"{name} - {qty} x {price} บาท")
        total += qty * price
        y -= 20

    tax = total * 0.07 if vat else 0
    grand_total = total + tax

    y -= 20
    c.drawString(50, y, f"รวม / Total: {total} บาท")
    c.drawString(50, y-20, f"VAT 7%: {tax:.2f} บาท")
    c.drawString(50, y-40, f"ยอดรวมทั้งหมด / Grand Total: {grand_total:.2f} บาท")

    c.save()
    buffer.seek(0)
    return buffer
