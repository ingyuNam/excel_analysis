import streamlit as st

from config import (
    GENAI_API_KEY,
    get_chart_path,
    get_matplotlib_font_path,
    register_korean_font,
)
from core.ai_analyzer import generate_analysis_code
from core.code_runner import AnalysisCodeError, run_analysis_code
from core.data_loader import (
    build_dataframe,
    describe_dataframe,
    detect_header_row,
    read_raw,
)
from core.pdf_report import build_report

st.title("📊 엑셀/데이터 분석 앱")

# 키가 없으면 분석 단계에서야 알 수 없는 에러로 터지므로 진입 시점에 막는다.
if not GENAI_API_KEY:
    st.error(
        "GENAI_API_KEY가 설정되지 않았습니다. "
        "로컬은 .env 파일에, 배포 환경은 앱 설정의 Secrets에 키를 넣어 주세요."
    )
    st.stop()

font_name = register_korean_font()
chart_path = get_chart_path()

# 세션상태 초기화 (새로고침 시 결과 유지 목적)
if "analysis_code" not in st.session_state:
    st.session_state.analysis_code = None

uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["xlsx", "csv"])

if uploaded_file is None:
    st.info("시작하려면 엑셀 또는 CSV 파일을 업로드해 주세요.")
    st.stop()

raw = read_raw(uploaded_file)
detected_row = detect_header_row(raw)

with st.expander("⚙️ 데이터 읽기 설정", expanded=False):
    st.caption(
        f"제목 행이나 빈 줄이 있는 파일도 읽을 수 있도록 헤더 위치를 자동으로 찾습니다. "
        f"현재 자동 감지 결과는 **{detected_row}번 행**입니다. 아래 원본에서 실제 "
        f"머리글 행 번호를 확인하고, 다르면 직접 바꿔주세요."
    )
    st.dataframe(raw.head(10))

    header_row = st.number_input(
        "머리글 행 번호",
        min_value=0,
        max_value=max(len(raw) - 1, 0),
        value=detected_row,
        step=1,
        key=f"header_row_{uploaded_file.name}",
    )
    fill_merged = st.checkbox(
        "병합된 셀 채우기",
        value=True,
        help="세로로 병합된 분류 칸(예: 축의금/조의금)의 빈 줄을 위 값으로 채웁니다.",
        key=f"fill_merged_{uploaded_file.name}",
    )

df = build_dataframe(raw, int(header_row), fill_merged)

if df.empty or len(df.columns) == 0:
    st.error("표를 읽지 못했습니다. '데이터 읽기 설정'에서 머리글 행 번호를 조정해 주세요.")
    st.stop()

st.subheader("📋 업로드된 데이터 미리보기")
st.dataframe(df.head())

if st.button("🚀 AI 자동 리포트 생성하기"):
    with st.spinner("🤖 데이터를 분석하고 리포트를 구성 중입니다..."):
        try:
            st.session_state.analysis_code = generate_analysis_code(describe_dataframe(df))
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

# 세션에 코드가 있으면 화면에 렌더링 및 PDF 다운로드 버튼 노출
if st.session_state.analysis_code:
    st.subheader("📈 AI 분석 리포트")
    # 화면에 렌더링된 내용이 그대로 기록되어 PDF 본문이 된다
    report_elements: list[dict] = []
    # 생성된 코드는 리포트 독자에게 의미 없는 정보라 평소엔 감추고, 실패했을 때만 편다.
    failed = False
    try:
        report_elements = run_analysis_code(
            st.session_state.analysis_code, df, chart_path, get_matplotlib_font_path()
        )
    except AnalysisCodeError as e:
        # 어디서 터졌는지 보여줘야 재생성이 나을지 데이터가 문제인지 판단할 수 있다.
        failed = True
        location = f" ({e.lineno}번째 줄)" if e.lineno else ""
        st.error(f"코드 실행 중 오류 발생{location}: {e}")
        if e.source_line:
            st.code(e.source_line, language="python")
        report_elements = e.elements  # 터지기 전까지 그려진 내용은 PDF에 살린다
        if report_elements:
            st.warning(
                "오류 지점 앞까지는 정상적으로 생성되었습니다. "
                "이 부분만으로 PDF를 받거나, 아래에서 리포트를 다시 생성해 보세요."
            )
    except Exception as e:
        failed = True
        st.error(f"코드 실행 중 오류 발생: {e}")

    if failed:
        with st.expander("🔍 생성된 분석 코드 전체 보기", expanded=False):
            st.code(st.session_state.analysis_code, language="python", line_numbers=True)

    st.markdown("---")
    st.subheader("📄 PDF 리포트 다운로드")

    if st.button("📥 분석 결과 PDF 생성하기"):
        try:
            # 차트 경로는 세션별 임시 디렉터리만 쓴다. 공유 경로로 폴백하면
            # 동시 접속 시 다른 사람의 차트가 내 PDF에 섞여 들어간다.
            pdf_buffer = build_report(
                df, uploaded_file.name, chart_path, font_name, report_elements
            )

            st.download_button(
                label="💾 PDF 파일 다운로드",
                data=pdf_buffer,
                file_name="AI_Data_Analysis_Report.pdf",
                mime="application/pdf",
            )
            st.success(
                "PDF 리포트가 준비되었습니다! 위의 'PDF 파일 다운로드' 버튼을 눌러주세요."
            )
        except Exception as pdf_err:
            st.error(f"PDF 생성 중 오류가 발생했습니다: {pdf_err}")
