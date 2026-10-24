"""把本次实验结果排成中文报告，不改动计算结果。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from receipts.narrative import report_pages


def main():
    font = os.environ.get("RECEIPTS_CJK_FONT", "C:/Windows/Fonts/simsun.ttc")
    if Path(font).is_file():
        pdfmetrics.registerFont(TTFont("Body", font, subfontIndex=0))
    else:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font = "STSong-Light"
    font_name = "Body" if font != "STSong-Light" else font
    body = ParagraphStyle("body", fontName=font_name, fontSize=10.5, leading=18,
                          firstLineIndent=21, alignment=TA_JUSTIFY, wordWrap="CJK", spaceAfter=10)
    title = ParagraphStyle("title", parent=body, fontSize=20, leading=28, firstLineIndent=0,
                           alignment=TA_CENTER, spaceAfter=12)
    heading = ParagraphStyle("heading", parent=body, fontSize=14, leading=21,
                             firstLineIndent=0, spaceBefore=5, spaceAfter=14)
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=14,
                          firstLineIndent=0, alignment=0, spaceAfter=0)
    manifest = json.loads((ROOT / "results" / "manifest.json").read_text(encoding="utf-8"))
    pages = report_pages(ROOT, manifest)
    story = []
    for i, page in enumerate(pages, 1):
        if i == 1:
            story += [Paragraph("项目收款多场景核对<br/>与月末差异分析", title),
                      Paragraph("模拟样例复现实验", ParagraphStyle("sub", parent=title, fontSize=11, leading=17)),
                      Spacer(1, 10)]
        story.append(Paragraph(f"{i}　{page['title']}", heading))
        # 第三页先展示比较结果，再说明评价与期间口径。
        paragraphs = [Paragraph(escape(p), body) for p in page["paragraphs"]]
        values = [[Paragraph(escape(str(v)), cell) for v in row]
                  for row in [page["headers"], *page["table"]]]
        n = len(page["headers"])
        ratios = ([.31, .18, .18, .16, .17] if i == 3 else
                  [.29, .29, .21, .21] if i == 4 else [1 / n] * n)
        table = Table(values, colWidths=[448 * r for r in ratios], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), .8, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), .5, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), .8, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        if i == 3:
            story += [table, Spacer(1, 16), *paragraphs]
        else:
            story += [*paragraphs, Spacer(1, 6), table]
        if i != len(pages):
            story.append(PageBreak())

    def footer(canvas, doc):
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(74, 32, "项目收款核对　模拟样例")
        canvas.drawRightString(A4[0] - 74, 32, str(doc.page))

    path = ROOT / "paper" / "main.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=73.5, rightMargin=73.5,
                            topMargin=61, bottomMargin=61, title="项目收款多场景核对与月末差异分析",
                            author="x29981412-maker")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(path)


if __name__ == "__main__":
    main()
