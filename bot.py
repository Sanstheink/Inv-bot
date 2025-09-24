import discord
from discord import app_commands
from discord.ext import commands
import os, datetime, json
from database import init_db, get_connection
from pdf_generator import create_document_pdf, create_invoice_pdf
from io import BytesIO

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
ADMIN_ROLE = os.getenv("ADMIN_ROLE", "Admin")

DOCUMENT_TYPES = [
    "หนังสือรับรอง", "รายงานประจำวัน", "รายงานประจำเดือน",
    "หนังสือขออนุมัติ", "หนังสืออนุมัติ", "ใบเสร็จรับเงิน", "ใบรับรองการชำระ"
]

# Modal สำหรับสร้างเอกสาร
class DocumentModal(discord.ui.Modal, title="สร้างเอกสาร"):
    doc_type = discord.ui.TextInput(label="ประเภทเอกสาร", placeholder="เช่น หนังสือรับรอง", style=discord.TextStyle.short)
    content = discord.ui.TextInput(label="เนื้อหาเอกสาร", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        title = f"{self.doc_type} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        pdf = create_document_pdf(title, self.content)
        conn = await get_connection()
        await conn.execute(
            "INSERT INTO documents(type, title, content, created_by) VALUES($1,$2,$3,$4)",
            self.doc_type, title, self.content, str(interaction.user)
        )
        await conn.close()
        await interaction.response.send_message(file=discord.File(fp=pdf, filename=f"{title}.pdf"))

# Modal สำหรับสร้างใบกำกับภาษี
class InvoiceModal(discord.ui.Modal, title="สร้างใบกำกับภาษี"):
    customer = discord.ui.TextInput(label="ชื่อลูกค้า")
    items_json = discord.ui.TextInput(label='รายการสินค้า/บริการ (JSON)', style=discord.TextStyle.paragraph, placeholder='[{"name":"สินค้า1","qty":1,"price":100}]')
    vat = discord.ui.TextInput(label="VAT 7%? (1=มี,0=ไม่มี)", style=discord.TextStyle.short, placeholder="1 หรือ 0")
    async def on_submit(self, interaction: discord.Interaction):
        items = json.loads(self.items_json)
        vat_bool = True if self.vat=="1" else False
        pdf = create_invoice_pdf(self.customer, items, vat_bool)
        total = sum([i['qty']*i['price'] for i in items])
        grand_total = total + (total*0.07 if vat_bool else 0)
        conn = await get_connection()
        await conn.execute(
            "INSERT INTO invoices(customer, items, vat, total, created_by) VALUES($1,$2,$3,$4,$5)",
            self.customer, json.dumps(items), vat_bool, grand_total, str(interaction.user)
        )
        await conn.close()
        await interaction.response.send_message(file=discord.File(fp=pdf, filename=f"Invoice-{self.customer}.pdf"))

# Dropdown สำหรับเลือกเอกสารย้อนหลัง
class DocumentDropdown(discord.ui.Select):
    def __init__(self, documents):
        options = [discord.SelectOption(label=d['title'], description=f"{d['type']} - {d['created_by']}", value=str(d['id'])) for d in documents]
        super().__init__(placeholder="เลือกเอกสาร...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        doc_id = int(self.values[0])
        conn = await get_connection()
        record = await conn.fetchrow("SELECT title, content FROM documents WHERE id=$1", doc_id)
        await conn.close()
        pdf = create_document_pdf(record['title'], record['content'])
        await interaction.response.send_message(file=discord.File(fp=pdf, filename=f"{record['title']}.pdf"))

class DocumentView(discord.ui.View):
    def __init__(self, documents):
        super().__init__()
        self.add_item(DocumentDropdown(documents))

# Modal สำหรับสร้างรายงาน PDF
class ReportModal(discord.ui.Modal, title="สร้างรายงานเอกสาร"):
    doc_type = discord.ui.TextInput(label="ประเภทเอกสาร (ว่าง=ทั้งหมด)", style=discord.TextStyle.short, required=False)
    start_date = discord.ui.TextInput(label="วันที่เริ่มต้น (YYYY-MM-DD)", style=discord.TextStyle.short, required=False)
    end_date = discord.ui.TextInput(label="วันที่สิ้นสุด (YYYY-MM-DD)", style=discord.TextStyle.short, required=False)
    async def on_submit(self, interaction: discord.Interaction):
        conn = await get_connection()
        query = "SELECT title, type, created_by, created_at FROM documents WHERE 1=1"
        params = []
        if self.doc_type.value: query += f" AND type=${len(params)+1}"; params.append(self.doc_type.value)
        if self.start_date.value: query += f" AND created_at >= ${len(params)+1}"; params.append(self.start_date.value)
        if self.end_date.value: query += f" AND created_at <= ${len(params)+1}"; params.append(self.end_date.value)
        if not any(role.name==ADMIN_ROLE for role in interaction.user.roles):
            query += f" AND created_by=${len(params)+1}"; params.append(str(interaction.user))
        records = await conn.fetch(query, *params)
        await conn.close()
        if not records:
            await interaction.response.send
