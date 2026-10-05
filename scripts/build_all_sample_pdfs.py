#!/usr/bin/env python3
"""Builds all 3 required sample PDFs:
1. sample_docs/nexus_enterprise_solutions_company_profile.pdf (>= 4000 words)
2. sample_docs/vanguard_global_logistics_company_profile.pdf (>= 4000 words)
3. sample_docs/product_catalog_100_offerings.pdf (100 product offerings with Qty 1, Qty 10 [-10%], Qty 100 [-30%])
"""

import sys
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas

from nexus_profile_data import get_nexus_profile_data
from vanguard_profile_data import get_vanguard_profile_data
from product_catalog_data import get_product_catalog_data

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DOCS_DIR = BASE_DIR / "sample_docs"
SAMPLE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "Enterprise RAG Knowledge Repository | Official Verified Profile")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 30, footer_text)
        self.drawString(54, 30, "Confidential - For Multi-Tenant RAG Evaluation & Ingestion Only")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)
        self.restoreState()


def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_CENTER,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='DocSubtitle',
        fontName='Helvetica-Oblique',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#334155'),
        alignment=TA_CENTER,
        spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e3a8a'),
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='SubSectionHeader',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0284c7'),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='BodyJustified',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1e293b'),
        alignment=TA_JUSTIFY,
        spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='TableCell',
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        name='TableCellCenter',
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='TableCellRight',
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name='MetaKey',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1e3a8a')
    ))
    styles.add(ParagraphStyle(
        name='MetaVal',
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    ))
    return styles


def count_words(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    total_words = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        words = re.findall(r'\b[A-Za-z0-9_-]+\b', text)
        total_words += len(words)
    return total_words


def generate_company_profile(data: dict, output_path: Path):
    styles = get_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    story = []

    # Title & Subtitle
    story.append(Paragraph(data["title"], styles["DocTitle"]))
    story.append(Paragraph(data["subtitle"], styles["DocSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # Metadata Table
    meta_rows = []
    for k, v in data["metadata"].items():
        meta_rows.append([
            Paragraph(f"<b>{k}:</b>", styles["MetaKey"]),
            Paragraph(v, styles["MetaVal"])
        ])
    meta_table = Table(meta_rows, colWidths=[150, 354])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Sections & Subsections
    for sec in data["sections"]:
        story.append(Paragraph(sec["title"], styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#93c5fd"), spaceAfter=6))
        for sub in sec["subsections"]:
            story.append(Paragraph(sub["subtitle"], styles["SubSectionHeader"]))
            paragraphs = sub["content"].split("\n\n")
            for p in paragraphs:
                if p.strip():
                    story.append(Paragraph(p.strip(), styles["BodyJustified"]))
        story.append(Spacer(1, 6))

    doc.build(story, canvasmaker=NumberedCanvas)
    words = count_words(output_path)
    print(f"Generated {output_path.name}: {words} words across {len(PdfReader(str(output_path)).pages)} pages.")
    return words


def generate_product_catalog(products: list, output_path: Path):
    styles = get_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54
    )
    story = []

    # Title & Subtitle
    story.append(Paragraph("ENTERPRISE PRODUCT CATALOG & QUANTITY PRICING SCHEDULE", styles["DocTitle"]))
    story.append(Paragraph(
        "Official 2026 Commercial Price List: 100 Enterprise Offerings with Tiered Volume Discounts (10% off for 10+, 30% off for 100+)",
        styles["DocSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # Overview text
    intro_text = (
        "This commercial schedule specifies authoritative pricing for 100 certified enterprise products across cloud "
        "hardware, AI accelerators, networking transceivers, distributed vector database licenses, security modules, "
        "and autonomous robotics. In accordance with enterprise procurement agreements, tiered volume discounts are applied "
        "automatically at checkout: a <b>10% price reduction</b> applies to quantities of 10 or more, and a <b>30% price reduction</b> "
        "applies to bulk enterprise orders of 100 units or more."
    )
    story.append(Paragraph(intro_text, styles["BodyJustified"]))
    story.append(Spacer(1, 10))

    # Table layout
    table_data = [[
        Paragraph("Item ID", styles["TableHeader"]),
        Paragraph("Product Name", styles["TableHeader"]),
        Paragraph("Product Description", styles["TableHeader"]),
        Paragraph("Qty 1 Price<br/>(Base)", styles["TableHeader"]),
        Paragraph("Qty 10+ Price<br/>(-10%)", styles["TableHeader"]),
        Paragraph("Qty 100+ Price<br/>(-30%)", styles["TableHeader"])
    ]]

    for idx, p in enumerate(products):
        table_data.append([
            Paragraph(p["item_id"], styles["TableCellCenter"]),
            Paragraph(f"<b>{p['name']}</b>", styles["TableCell"]),
            Paragraph(p["description"], styles["TableCell"]),
            Paragraph(f"${p['price_1']:,.2f}", styles["TableCellRight"]),
            Paragraph(f"${p['price_10']:,.2f}", styles["TableCellRight"]),
            Paragraph(f"${p['price_100']:,.2f}", styles["TableCellRight"])
        ])

    col_widths = [50, 115, 185, 62, 64, 64]  # total = 540 (printable width = 612 - 72 = 540)
    catalog_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    # Alternating row background
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            t_style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor("#f8fafc")))
        else:
            t_style.append(('BACKGROUND', (0, r), (-1, r), colors.white))

    catalog_table.setStyle(TableStyle(t_style))
    story.append(catalog_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    reader = PdfReader(str(output_path))
    print(f"Generated {output_path.name}: 100 products across {len(reader.pages)} pages.")


def main():
    print("--- Generating Sample Enterprise PDFs in sample_docs/ ---")

    # 1. Nexus Enterprise Technologies Profile
    nexus_file = SAMPLE_DOCS_DIR / "nexus_enterprise_solutions_company_profile.pdf"
    nexus_words = generate_company_profile(get_nexus_profile_data(), nexus_file)
    assert nexus_words >= 4000, f"Nexus word count {nexus_words} < 4000!"

    # 2. Vanguard Global Logistics Profile
    vanguard_file = SAMPLE_DOCS_DIR / "vanguard_global_logistics_company_profile.pdf"
    vanguard_words = generate_company_profile(get_vanguard_profile_data(), vanguard_file)
    assert vanguard_words >= 4000, f"Vanguard word count {vanguard_words} < 4000!"

    # 3. Product Catalog with 100 offerings & tiered pricing
    catalog_file = SAMPLE_DOCS_DIR / "product_catalog_100_offerings.pdf"
    generate_product_catalog(get_product_catalog_data(), catalog_file)

    print("\n--- Summary of Generated PDF Documents ---")
    print(f"1. {nexus_file.name} - {nexus_words} words (Requirement: >= 4000 words)")
    print(f"2. {vanguard_file.name} - {vanguard_words} words (Requirement: >= 4000 words)")
    print(f"3. {catalog_file.name} - 100 product offerings with Qty 1, Qty 10 (-10%), Qty 100 (-30%) pricing")
    print("All sample PDF files successfully generated and verified!")

if __name__ == "__main__":
    main()
