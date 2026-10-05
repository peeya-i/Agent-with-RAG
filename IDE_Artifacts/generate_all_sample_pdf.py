#!/usr/bin/env python3
"""Generator for:
1. sample_docs/nexus_enterprise_solutions_company_profile.pdf (>= 4000 words)
2. sample_docs/vanguard_global_logistics_company_profile.pdf (>= 4000 words)
3. sample_docs/product_catalog_100_offerings.pdf (100 products with tiered pricing)
"""

import re
from pathlib import Path
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas

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
            self.drawString(54, letter[1] - 36, "Enterprise Knowledge Document | Verified Reference Profile")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 30, footer_text)
        self.drawString(54, 30, "Confidential - Multi-Tenant RAG & Enterprise Autonomous Architecture")
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
        name='BulletItem',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1e293b'),
        leftIndent=12,
        spaceAfter=3
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
    return styles

def count_words(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    total_words = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        words = re.findall(r'\b[A-Za-z0-9_-]+\b', text)
        total_words += len(words)
    return total_words
