import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"
PROMPT_DIR = BASE_DIR / "prompts"

# 본문/볼드용 후보를 순서대로 탐색한다. 정적 웨이트가 없으면 가변 폰트로 폴백.
_REGULAR_CANDIDATES = ["SUIT-Regular.ttf", "SUIT-Medium.ttf", "SUIT-Variable.ttf"]
_BOLD_CANDIDATES = ["SUIT-Bold.ttf", "SUIT-SemiBold.ttf", "SUIT-ExtraBold.ttf"]


def _get_secret(name: str) -> str | None:
    """로컬(.env)과 Streamlit Cloud(Secrets) 양쪽에서 키를 읽는다.

    Cloud에는 .env가 없고 로컬에는 secrets.toml이 없을 수 있으므로,
    한쪽이 비어 있어도 죽지 않게 순서대로 훑는다.
    StreamlitSecretNotFoundError가 FileNotFoundError를 상속하므로 함께 걸린다.
    """
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError):
        return None


GENAI_API_KEY = _get_secret("GENAI_API_KEY")
GENAI_MODEL = "gemini-3.6-flash"


def _find_font(candidates: list[str]) -> Path | None:
    for name in candidates:
        path = FONT_DIR / name
        if path.exists():
            return path
    return None


@st.cache_resource
def register_korean_font() -> str:
    """PDF용 한글 폰트를 등록하고 본문 폰트명을 반환한다.

    캐시를 걸어 리런마다 registerFont가 다시 호출되지 않게 한다.
    """
    regular = _find_font(_REGULAR_CANDIDATES)
    if regular is None:
        return "Helvetica"

    pdfmetrics.registerFont(TTFont("SUIT", str(regular)))

    # <b> 태그가 Helvetica-Bold로 폴백해 한글이 깨지지 않도록 패밀리를 매핑한다.
    # 볼드 파일이 없으면 볼드 자리에도 본문 폰트를 물려 최소한 글자는 살린다.
    bold = _find_font(_BOLD_CANDIDATES)
    if bold is not None:
        pdfmetrics.registerFont(TTFont("SUIT-Bold", str(bold)))
        bold_name = "SUIT-Bold"
    else:
        bold_name = "SUIT"

    for italic in (0, 1):
        addMapping("SUIT", 0, italic, "SUIT")
        addMapping("SUIT", 1, italic, bold_name)

    return "SUIT"


def get_matplotlib_font_path() -> str | None:
    """생성된 코드에서 matplotlib 한글 폰트로 쓸 경로. 없으면 None.

    가변 폰트는 matplotlib이 기본 인스턴스(Thin)로 읽어 지나치게 얇게 나오므로
    정적 Regular 파일을 우선한다.
    """
    regular = _find_font(_REGULAR_CANDIDATES)
    return str(regular) if regular else None


def get_chart_path() -> str:
    """세션마다 독립된 차트 이미지 경로.

    동시 접속 시 서로의 차트를 덮어쓰던 문제를 막기 위해 세션별 임시 디렉터리를 쓴다.
    """
    if "chart_path" not in st.session_state:
        st.session_state.chart_path = str(Path(tempfile.mkdtemp()) / "chart.png")
    return st.session_state.chart_path
