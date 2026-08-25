import io
import os
import re
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_WIDTH = A4[0] - 80  # 좌우 여백 40씩 제외한 사용 가능 폭
MAX_TABLE_ROWS = 15
MAX_TABLE_COLS = 8

# 지표 값이 칸을 넘칠 때 이 순서로 줄여 본다. 마지막 크기로도 안 맞으면 줄바꿈한다.
METRIC_VALUE_SIZES = (13, 12, 11, 10, 9, 8)
METRIC_CELL_PADDING = 12  # 셀 좌우 패딩 합계


def _bold_of(font_name: str) -> str:
    """등록되어 있으면 볼드 폰트명을, 없으면 본문 폰트명을 그대로 돌려준다."""
    bold = f"{font_name}-Bold"
    return bold if bold in pdfmetrics.getRegisteredFontNames() else font_name


def _build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    bold_name = _bold_of(font_name)
    return {
        "title": ParagraphStyle(
            "KoreanTitle", parent=base, fontName=bold_name, fontSize=18, leading=22,
            textColor=colors.HexColor("#1f77b4"), spaceAfter=15, keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "KoreanH2", parent=base, fontName=bold_name, fontSize=14, leading=18,
            textColor=colors.HexColor("#1f77b4"), spaceBefore=12, spaceAfter=8, keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "KoreanH3", parent=base, fontName=bold_name, fontSize=12, leading=16,
            textColor=colors.HexColor("#444444"), spaceBefore=10, spaceAfter=6, keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "KoreanBody", parent=base, fontName=font_name, fontSize=10, leading=14,
            textColor=colors.HexColor("#333333"), spaceAfter=10,
        ),
    }


def _md_to_rl(text: str) -> str:
    """마크다운 강조를 ReportLab 인라인 태그로. 나머지 마크업은 제거한다."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text.replace("\n", "<br/>")


def _image_flowable(png: bytes, max_width: float = PAGE_WIDTH) -> RLImage:
    """원본 비율을 지키면서 페이지 폭에 맞춰 축소한다."""
    width, height = ImageReader(io.BytesIO(png)).getSize()
    scale = min(max_width / width, 1.0)
    return RLImage(io.BytesIO(png), width=width * scale, height=height * scale)


def _fit_font_size(texts: list[str], font_name: str, available: float) -> float:
    """모든 값이 칸 안에 들어가는 가장 큰 글자 크기. 다 안 맞으면 최소 크기."""
    for size in METRIC_VALUE_SIZES:
        if all(pdfmetrics.stringWidth(t, font_name, size) <= available for t in texts):
            return size
    return METRIC_VALUE_SIZES[-1]


def _metric_table(metrics: list[dict], font_name: str) -> Table:
    """연속된 st.metric들을 한 줄짜리 카드 형태로 묶는다.

    셀에 평문 문자열을 넣으면 ReportLab이 줄바꿈하지 않고 칸 밖으로 흘려보낸다.
    "2,551,455,598원" 같은 긴 금액이 옆 칸을 침범하므로, Paragraph로 감싸 줄바꿈이
    가능하게 하고 글자 크기도 칸 폭에 맞춰 줄인다.
    """
    labels = [m["label"] for m in metrics]
    values = [m["value"] + (f" ({m['delta']})" if m.get("delta") else "") for m in metrics]
    col_width = PAGE_WIDTH / len(metrics)
    available = col_width - METRIC_CELL_PADDING
    bold_name = _bold_of(font_name)
    value_size = _fit_font_size(values, bold_name, available)

    label_style = ParagraphStyle(
        "MetricLabel", fontName=font_name, fontSize=9, leading=11,
        alignment=TA_CENTER, textColor=colors.HexColor("#6c757d"),
    )
    value_style = ParagraphStyle(
        "MetricValue", fontName=bold_name, fontSize=value_size, leading=value_size + 3,
        alignment=TA_CENTER, textColor=colors.HexColor("#212529"),
    )
    rows = [
        [Paragraph(escape(text), label_style) for text in labels],
        [Paragraph(escape(text), value_style) for text in values],
    ]
    table = Table(rows, colWidths=[col_width] * len(metrics))
    # 글꼴·정렬·색은 Paragraph가 들고 있으므로 표에는 테두리와 여백만 남긴다.
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), METRIC_CELL_PADDING / 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), METRIC_CELL_PADDING / 2),
        ])
    )
    return table


def _df_table(df: pd.DataFrame, font_name: str) -> Table:
    """데이터프레임을 표로. 페이지에 들어가도록 행/열을 제한한다."""
    trimmed = df.iloc[:MAX_TABLE_ROWS, :MAX_TABLE_COLS]
    header = [str(c) for c in trimmed.columns]
    rows = [[str(v) for v in row] for row in trimmed.itertuples(index=False)]
    col_width = PAGE_WIDTH / max(len(header), 1)
    table = Table([header] + rows, colWidths=[col_width] * len(header), repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTNAME", (0, 0), (-1, 0), _bold_of(font_name)),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return table


def _summary_table(df: pd.DataFrame, font_name: str) -> Table:
    rows = [
        ["총 행 수", f"{len(df):,} 행"],
        ["총 열 수", f"{len(df.columns)} 개"],
        ["주요 컬럼", ", ".join(str(c) for c in list(df.columns)[:5])],
    ]
    table = Table(rows, colWidths=[100, PAGE_WIDTH - 100])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTNAME", (0, 0), (0, -1), _bold_of(font_name)),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return table


def _render_elements(elements: list[dict], styles: dict, font_name: str) -> list:
    """기록된 화면 요소들을 순서 그대로 PDF 플로어블로 변환한다."""
    story = []
    pending_metrics: list[dict] = []

    def flush_metrics():
        if pending_metrics:
            story.append(_metric_table(pending_metrics, font_name))
            story.append(Spacer(1, 12))
            pending_metrics.clear()

    for el in elements:
        kind = el.get("type")

        # metric은 연달아 나오면 한 줄로 묶어야 하므로 따로 모은다
        if kind == "metric":
            pending_metrics.append(el)
            if len(pending_metrics) == 4:  # 한 줄에 4개까지
                flush_metrics()
            continue
        flush_metrics()

        if kind == "text":
            text = (el.get("text") or "").strip()
            if not text:
                continue
            style = {1: "title", 2: "h2", 3: "h3"}.get(el.get("level", 0), "body")
            story.append(Paragraph(_md_to_rl(text), styles[style]))

        elif kind == "image":
            story.append(KeepTogether([_image_flowable(el["png"]), Spacer(1, 12)]))

        elif kind == "table":
            story.append(_df_table(el["df"], font_name))
            story.append(Spacer(1, 12))

        elif kind == "missing_chart":
            story.append(Paragraph(
                "<i>(인터랙티브 차트는 PDF로 변환할 수 없어 생략되었습니다)</i>",
                styles["body"],
            ))

        elif kind == "divider":
            story.append(Spacer(1, 10))

    flush_metrics()
    return story


def build_report(
    df: pd.DataFrame,
    source_name: str,
    chart_path: str,
    font_name: str,
    elements: list[dict] | None = None,
) -> io.BytesIO:
    """분석 결과 PDF를 만들어 버퍼로 반환한다. Streamlit에 의존하지 않는 순수 함수.

    elements는 화면에 렌더링된 내용의 기록이며, 있으면 그대로 리포트 본문이 된다.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40,
    )
    styles = _build_styles(font_name)
    story = [
        Paragraph("AI 엑셀 데이터 분석 리포트", styles["title"]),
        Paragraph(f"파일명: {source_name}", styles["body"]),
        Spacer(1, 10),
        _summary_table(df, font_name),
        Spacer(1, 15),
    ]

    body = _render_elements(elements or [], styles, font_name)
    if body:
        story.extend(body)
    elif chart_path and os.path.exists(chart_path):
        # 기록이 없을 때를 위한 폴백: 파일로 저장된 차트만이라도 싣는다
        story.append(Paragraph("<b>[주요 시각화 분석 차트]</b>", styles["body"]))
        story.append(Spacer(1, 5))
        story.append(RLImage(chart_path, width=400, height=240))
        story.append(Spacer(1, 15))

    doc.build(story)
    buffer.seek(0)
    return buffer
