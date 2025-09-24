import discord
from discord.ext import commands
from discord import app_commands
import psycopg2, datetime, io, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from discord.ui import View, Select

# ======================= Config =======================
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================= Database =======================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_number TEXT,
        title TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id SERIAL PRIMARY KEY,
        invoice_number TEXT,
        customer TEXT,
        items TEXT,
        total FLOAT,
        vat FLOAT,
        grand_total FLOAT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id SERIAL PRIMARY KEY,
        receipt_number TEXT,
        shop TEXT,
        customer TEXT,
        items TEXT,
        total FLOAT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# ======================= Helper Functions =======================
def generate_number(prefix, table):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0] + 1
    cur.close()
    conn.close()
    year = datetime.datetime.now().year
    return f"{prefix}-{year}-{count:03d}"

# ======================= PDF Generators =======================
def generate_pdf_doc(doc_number, title, content):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 820, "เอกสารภายในหน่วยงาน")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 790, f"เลขที่: {doc_number}")
    pdf.drawString(50, 770, f"เรื่อง: {title}")
    pdf.drawString(50, 750, f"วันที่: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    text = pdf.beginText(50, 720)
    text.setFont("Helvetica", 11)
    for line in content.split("\n"):
        text.textLine(line)
    pdf.drawText(text)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

def generate_pdf_invoice(invoice_number, customer, items, total):
    vat = total * 0.07
    grand_total = total + vat
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 820, "ใบกำกับภาษี / TAX INVOICE")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 790, f"เลขที่: {invoice_number}")
    pdf.drawString(50, 770, f"ลูกค้า: {customer}")
    pdf.drawString(50, 750, f"วันที่: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.drawString(50, 720, f"รายการ: {items}")
    pdf.drawString(50, 690, f"ยอดก่อน VAT: {total:.2f} บาท")
    pdf.drawString(50, 670, f"VAT (7%): {vat:.2f} บาท")
    pdf.drawString(50, 650, f"รวมสุทธิ: {grand_total:.2f} บาท")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer, vat, grand_total

def generate_pdf_receipt(receipt_number, shop, customer, items, total):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 820, "ใบเสร็จรับเงิน / RECEIPT")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 790, f"เลขที่: {receipt_number}")
    pdf.drawString(50, 770, f"ร้านค้า: {shop}")
    pdf.drawString(50, 750, f"ลูกค้า: {customer}")
    pdf.drawString(50, 730, f"วันที่: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.drawString(50, 700, f"รายการ: {items}")
    pdf.drawString(50, 670, f"จำนวนเงิน: {total:.2f} บาท")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

# ======================= Permission =======================
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.manage_guild

# ======================= Slash Commands =======================
@bot.tree.command(name="createdoc", description="สร้างเอกสารภายในหน่วยงาน (Admin เท่านั้น)")
async def createdoc(interaction: discord.Interaction, title: str, content: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์", ephemeral=True)
        return

    doc_number = generate_number("DOC", "documents")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO documents (doc_number, title, content) VALUES (%s, %s, %s)",
                (doc_number, title, content))
    conn.commit()
    cur.close()
    conn.close()

    pdf_buffer = generate_pdf_doc(doc_number, title, content)
    await interaction.response.send_message(f"✅ เอกสาร `{doc_number}` ถูกสร้าง", file=discord.File(pdf_buffer, filename=f"{doc_number}.pdf"))

@bot.tree.command(name="invoice", description="ออกใบกำกับภาษี (Admin เท่านั้น)")
async def invoice(interaction: discord.Interaction, customer: str, items: str, total: float):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์", ephemeral=True)
        return

    invoice_number = generate_number("INV", "invoices")
    pdf_buffer, vat, grand_total = generate_pdf_invoice(invoice_number, customer, items, total)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO invoices (invoice_number, customer, items, total, vat, grand_total) VALUES (%s,%s,%s,%s,%s,%s)",
                (invoice_number, customer, items, total, vat, grand_total))
    conn.commit()
    cur.close()
    conn.close()

    await interaction.response.send_message(f"✅ ใบกำกับภาษี `{invoice_number}` สร้างแล้ว\n💰 รวม: {grand_total:.2f} บาท",
                                            file=discord.File(pdf_buffer, filename=f"{invoice_number}.pdf"))

@bot.tree.command(name="receipt", description="ออกใบเสร็จรับเงิน (Admin เท่านั้น)")
async def receipt(interaction: discord.Interaction, shop: str, customer: str, items: str, total: float):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์", ephemeral=True)
        return

    receipt_number = generate_number("RC", "receipts")
    pdf_buffer = generate_pdf_receipt(receipt_number, shop, customer, items, total)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO receipts (receipt_number, shop, customer, items, total) VALUES (%s,%s,%s,%s,%s)",
                (receipt_number, shop, customer, items, total))
    conn.commit()
    cur.close()
    conn.close()

    await interaction.response.send_message(f"✅ ใบเสร็จ `{receipt_number}` สร้างแล้ว\n💰 ยอดรวม: {total:.2f} บาท",
                                            file=discord.File(pdf_buffer, filename=f"{receipt_number}.pdf"))

# ======================= Dropdown =======================
class DocumentDropdown(Select):
    def __init__(self, rows, doc_type):
        options = []
        for r in rows:
            if doc_type == "doc":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]}", description=f"ID {r[0]} | {r[3]}", value=str(r[0])))
            elif doc_type == "invoice":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]}", description=f"ID {r[0]} | {r[4]:.2f}฿ | {r[3]}", value=str(r[0])))
            elif doc_type == "receipt":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]} ({r[3]})", description=f"ID {r[0]} | {r[5]:.2f}฿ | {r[4]}", value=str(r[0])))
        super().__init__(placeholder="เลือกเอกสาร...", min_values=1, max_values=1, options=options)
        self.doc_type = doc_type

    async def callback(self, interaction: discord.Interaction):
        doc_id = int(self.values[0])
        conn = get_conn()
        cur = conn.cursor()

        if self.doc_type == "doc":
            cur.execute("SELECT * FROM documents WHERE id=%s", (doc_id,))
            doc = cur.fetchone()
            pdf_buffer = generate_pdf_doc(doc[1], doc[2], doc[3])
            file = discord.File(pdf_buffer, filename=f"{doc[1]}.pdf")
            await interaction.response.send_message(f"📄 เอกสาร `{doc[1]}`", file=file, ephemeral=True)

        elif self.doc_type == "invoice":
            cur.execute("SELECT * FROM invoices WHERE id=%s", (doc_id,))
            inv = cur.fetchone()
            pdf_buffer, _, _ = generate_pdf_invoice(inv[1], inv[2], inv[3], inv[4])
            file = discord.File(pdf_buffer, filename=f"{inv[1]}.pdf")
            await interaction.response.send_message(f"📑 ใบกำกับภาษี `{inv[1]}`", file=file, ephemeral=True)

        elif self.doc_type == "receipt":
            cur.execute("SELECT * FROM receipts WHERE id=%s", (doc_id,))
            rec = cur.fetchone()
            pdf_buffer = generate_pdf_receipt(rec[1], rec[2], rec[3],)
