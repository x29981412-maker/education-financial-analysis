"""将公开数据分析整理为四页中文研究报告。"""

import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from analysis import ROOT, research_sections, run


def main():
    data, indicators, checks, bridge = run()
    path = Path(os.environ.get("RESEARCH_CJK_FONT", "C:/Windows/Fonts/simsun.ttc"))
    if path.exists():
        pdfmetrics.registerFont(TTFont("Song", str(path), subfontIndex=0))
        font = "Song"
    else:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font = "STSong-Light"
    body = ParagraphStyle("body", fontName=font, fontSize=10.5, leading=18,
                          firstLineIndent=21, spaceAfter=11, wordWrap="CJK", alignment=TA_JUSTIFY)
    heading = ParagraphStyle("heading", parent=body, fontSize=14, leading=21, firstLineIndent=0, spaceAfter=15)
    title = ParagraphStyle("title", parent=body, fontSize=20, leading=29, firstLineIndent=0, alignment=TA_CENTER, spaceAfter=12)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=13, firstLineIndent=0)
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=14, firstLineIndent=0, spaceAfter=0, alignment=0)
    story = []
    for i, section in enumerate(research_sections(data, indicators, checks, bridge), 1):
        if i == 1:
            story += [Paragraph("教育企业财务数据核验<br/>与现金流分析", title),
                      Paragraph("以新东方2023—2025财年为例", ParagraphStyle("subtitle", parent=title, fontSize=11, leading=18)),
                      Spacer(1, 10)]
        story.append(Paragraph(f"{i}　{section['title']}", heading))
        story += [Paragraph(escape(p), body) for p in section["paragraphs"]]
        if i == 3:
            drawing = Drawing(448, 151)
            chart = VerticalBarChart()
            chart.x, chart.y, chart.width, chart.height = 42, 25, 350, 103
            chart.data = [tuple(float(r["net_income_usd_million"]) for r in indicators),
                          tuple(float(r["operating_cf_usd_million"]) for r in indicators)]
            chart.categoryAxis.categoryNames = ["2023", "2024", "2025"]
            chart.categoryAxis.labels.fontName = font
            chart.categoryAxis.labels.fontSize = 8
            chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 1200, 300
            chart.valueAxis.labels.fontName = font
            chart.valueAxis.labels.fontSize = 8
            chart.bars[0].fillColor = colors.HexColor("#A5A5A5")
            chart.bars[1].fillColor = colors.HexColor("#333333")
            chart.bars.strokeWidth = 0
            drawing.add(chart)
            drawing.add(String(8, 135, "百万美元", fontName=font, fontSize=8))
            drawing.add(Rect(210, 135, 8, 6, fillColor=colors.HexColor("#A5A5A5"), strokeColor=None))
            drawing.add(String(224, 134, "合并净利润", fontName=font, fontSize=8))
            drawing.add(Rect(306, 135, 8, 6, fillColor=colors.HexColor("#333333"), strokeColor=None))
            drawing.add(String(320, 134, "经营现金流", fontName=font, fontSize=8))
            story += [drawing, Spacer(1, 7)]
        table_data = [[Paragraph(escape(str(v)), cell) for v in row]
                      for row in [section["headers"], *section["table"]]]
        widths = [.4, .2, .2, .2] if i == 1 else [.38, .21, .16, .25] if i == 2 else [.7, .3] if i == 3 else [.34, .22, .22, .22]
        table = Table(table_data, colWidths=[448 * w for w in widths], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), .7, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), .5, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), .7, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F3F3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story += [table, Spacer(1, 8), Paragraph(escape(section["source"]), small)]
        if i == 4:
            url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0925/2025092501682.pdf"
            story += [Spacer(1, 12), Paragraph(f'原始资料：<link href="{url}">港交所披露易，新东方2025年报，2025年9月25日。</link>', small)]
        if i < 4:
            story.append(PageBreak())

    def footer(canvas, doc):
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(74, 32, "教育企业财务分析　小组研究")
        canvas.drawRightString(A4[0] - 74, 32, str(doc.page))

    doc = SimpleDocTemplate(str(ROOT / "paper" / "main.pdf"), pagesize=A4,
                            leftMargin=73.5, rightMargin=73.5, topMargin=60, bottomMargin=60,
                            title="教育企业财务数据核验与现金流分析", author="路顺翔")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    main()
