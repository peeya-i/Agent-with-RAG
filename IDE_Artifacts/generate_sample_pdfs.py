#!/usr/bin/env python3
"""Comprehensive script to generate:
1. sample_docs/nexus_enterprise_solutions_company_profile.pdf (>= 4000 words)
2. sample_docs/vanguard_global_logistics_company_profile.pdf (>= 4000 words)
3. sample_docs/product_catalog_100_offerings.pdf (100 products with tiered pricing: 1x, 10x -10%, 100x -30%)
"""

import os
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

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent / "sample_docs"
SAMPLE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

class NumberedCanvas(canvas.Canvas):
    """Canvas that performs a two-pass rendering to write 'Page X of Y'."""
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
            self.drawString(54, letter[1] - 36, "Enterprise RAG Sample Knowledge Library | Corporate Reference Document")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 30, footer_text)
        self.drawString(54, 30, "Confidential - For Multi-Tenant RAG Knowledge Base Evaluation Only")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)
        self.restoreState()


def get_custom_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='DocTitle',
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_CENTER,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='DocSubtitle',
        fontName='Helvetica-Oblique',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#334155'),
        alignment=TA_CENTER,
        spaceAfter=15
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1e3a8a'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='SubSectionHeader',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#0369a1'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='BodyJustified',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='BulletItem',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        leftIndent=14,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='TableCell',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        name='TableCellCenter',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='TableCellRight',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0f172a'),
        alignment=TA_RIGHT
    ))
    return styles

def count_pdf_words(filepath: Path) -> int:
    reader = PdfReader(str(filepath))
    total_words = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        words = re.findall(r'\b[A-Za-z0-9_-]+\b', text)
        total_words += len(words)
    return total_words
