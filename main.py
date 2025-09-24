import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, datetime, io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from discord.ui import View, Select

TOKEN = "YOUR_DISCORD_BOT_TOKEN"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================= Database Setup =======================
def init_db():
    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doc_number TEXT,
                  title TEXT,
                  content TEXT,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  invoice_number TEXT,
                  customer TEXT,
                  items TEXT,
                  total REAL,
                  vat REAL,
                  grand_total REAL,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receipts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  receipt_number TEXT,
                  shop TEXT,
                  customer TEXT,
                  items TEXT,
                  total REAL,
                  created_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ======================= Helper Function: Running Number =======================
def generate_number(prefix, table, column):
    year = datetime.datetime.now().year
    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM {table}")
    count = c.fetchone()[0] + 1
    conn.close()
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

# ======================= Permission Check =======================
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.manage_guild

# ======================= Slash Commands (Create) =======================
@bot.tree.command(name="createdoc", description="สร้างเอกสารภายในหน่วยงาน (Admin เท่านั้น)")
async def createdoc(interaction: discord.Interaction, title: str, content: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        return

    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    doc_number = generate_number("DOC", "documents", "doc_number")

    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("INSERT INTO documents (doc_number, title, content, created_at) VALUES (?, ?, ?, ?)",
              (doc_number, title, content, created_at))
    conn.commit()
    conn.close()

    pdf_buffer = generate_pdf_doc(doc_number, title, content)
    await interaction.response.send_message(
        f"✅ เอกสาร `{doc_number}` ถูกสร้างเรียบร้อย", 
        file=discord.File(pdf_buffer, filename=f"{doc_number}.pdf")
    )

@bot.tree.command(name="invoice", description="ออกใบกำกับภาษี (Admin เท่านั้น)")
async def invoice(interaction: discord.Interaction, customer: str, items: str, total: float):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        return

    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    invoice_number = generate_number("INV", "invoices", "invoice_number")
    pdf_buffer, vat, grand_total = generate_pdf_invoice(invoice_number, customer, items, total)

    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("INSERT INTO invoices (invoice_number, customer, items, total, vat, grand_total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (invoice_number, customer, items, total, vat, grand_total, created_at))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"✅ ใบกำกับภาษี `{invoice_number}` ถูกสร้างแล้ว\n💰 รวมสุทธิ: {grand_total:.2f} บาท",
        file=discord.File(pdf_buffer, filename=f"{invoice_number}.pdf")
    )

@bot.tree.command(name="receipt", description="ออกใบเสร็จรับเงิน (Admin เท่านั้น)")
async def receipt(interaction: discord.Interaction, shop: str, customer: str, items: str, total: float):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        return

    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    receipt_number = generate_number("RC", "receipts", "receipt_number")
    pdf_buffer = generate_pdf_receipt(receipt_number, shop, customer, items, total)

    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("INSERT INTO receipts (receipt_number, shop, customer, items, total, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (receipt_number, shop, customer, items, total, created_at))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"✅ ใบเสร็จรับเงิน `{receipt_number}` ถูกสร้างแล้ว\n💰 ยอดรวม: {total:.2f} บาท",
        file=discord.File(pdf_buffer, filename=f"{receipt_number}.pdf")
    )

# ======================= Dropdown Helper =======================
class DocumentDropdown(Select):
    def __init__(self, rows, doc_type):
        options = []
        for r in rows:
            if doc_type == "doc":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]}", description=f"ID {r[0]} | {r[3]}", value=str(r[0])))
            elif doc_type == "invoice":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]}", description=f"ID {r[0]} | {r[4]} | {r[3]:.2f}฿", value=str(r[0])))
            elif doc_type == "receipt":
                options.append(discord.SelectOption(label=f"{r[1]} - {r[2]} ({r[3]})", description=f"ID {r[0]} | {r[5]} | {r[4]:.2f}฿", value=str(r[0])))
        super().__init__(placeholder="เลือกเอกสารที่ต้องการ...", min_values=1, max_values=1, options=options)
        self.doc_type = doc_type

    async def callback(self, interaction: discord.Interaction):
        doc_id = int(self.values[0])

        conn = sqlite3.connect("documents.db")
        c = conn.cursor()

        if self.doc_type == "doc":
            c.execute("SELECT * FROM documents WHERE id=?", (doc_id,))
            doc = c.fetchone()
            pdf_buffer = generate_pdf_doc(doc[1], doc[2], doc[3])
            file = discord.File(pdf_buffer, filename=f"{doc[1]}.pdf")
            await interaction.response.send_message(f"📄 เอกสาร `{doc[1]}`", file=file, ephemeral=True)

        elif self.doc_type == "invoice":
            c.execute("SELECT * FROM invoices WHERE id=?", (doc_id,))
            inv = c.fetchone()
            pdf_buffer, _, _ = generate_pdf_invoice(inv[1], inv[2], inv[3], inv[4])
            file = discord.File(pdf_buffer, filename=f"{inv[1]}.pdf")
            await interaction.response.send_message(f"📑 ใบกำกับภาษี `{inv[1]}`", file=file, ephemeral=True)

        elif self.doc_type == "receipt":
            c.execute("SELECT * FROM receipts WHERE id=?", (doc_id,))
            rec = c.fetchone()
            pdf_buffer = generate_pdf_receipt(rec[1], rec[2], rec[3], rec[4], rec[5])
            file = discord.File(pdf_buffer, filename=f"{rec[1]}.pdf")
            await interaction.response.send_message(f"🧾 ใบเสร็จ `{rec[1]}`", file=file, ephemeral=True)

        conn.close()

class DocumentView(View):
    def __init__(self, rows, doc_type):
        super().__init__()
        self.add_item(DocumentDropdown(rows, doc_type))

# ======================= List Commands =======================
@bot.tree.command(name="listdocs", description="แสดงรายการเอกสาร (เลือกจากเมนู)")
async def listdocs(interaction: discord.Interaction):
    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("SELECT id, doc_number, title, created_at FROM documents ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("❌ ยังไม่มีเอกสารในระบบ")
        return

    await interaction.response.send_message("📄 เลือกเอกสารจากเมนู:", view=DocumentView(rows, "doc"), ephemeral=True)

@bot.tree.command(name="listinvoices", description="แสดงรายการใบกำกับภาษี (เลือกจากเมนู)")
async def listinvoices(interaction: discord.Interaction):
    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("SELECT id, invoice_number, customer, grand_total, created_at FROM invoices ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("❌ ยังไม่มีใบกำกับภาษีในระบบ")
        return

    await interaction.response.send_message("📑 เลือกใบกำกับภาษีจากเมนู:", view=DocumentView(rows, "invoice"), ephemeral=True)

@bot.tree.command(name="listreceipts", description="แสดงรายการใบเสร็จ (เลือกจากเมนู)")
async def listreceipts(interaction: discord.Interaction):
    conn = sqlite3.connect("documents.db")
    c = conn.cursor()
    c.execute("SELECT id, receipt_number, shop, customer, total, created_at FROM receipts ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("❌ ยังไม่มีใบเสร็จในระบบ")
        return

    await interaction.response.send_message("🧾 เลือกใบเสร็จจากเมนู:", view=DocumentView(rows, "receipt"), ephemeral=True)

# ======================= Bot Ready =======================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot {bot.user} พร้อมใช้งานแล้ว")

bot.run(TOKEN)
