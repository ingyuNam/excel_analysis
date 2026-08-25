import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core.report_recorder import ReportRecorder, recording_streamlit


def run_analysis_code(
    code: str, df: pd.DataFrame, chart_path: str, font_path: str | None
) -> list[dict]:
    """생성된 분석 코드를 실행하고, 화면에 렌더링된 내용을 PDF용 구조로 돌려준다.

    globals 자리에 네임스페이스 딕셔너리 하나만 넘기는 것이 핵심이다.
    locals를 따로 넘기면 컴프리헨션·중첩 스코프에서 이름을 찾지 못해 NameError가 난다.
    """
    recorder = ReportRecorder()
    namespace = {
        "df": df,
        "st": recording_streamlit(st, recorder),
        "pd": pd,
        "plt": plt,
        "CHART_PATH": chart_path,
        "FONT_PATH": font_path,
    }
    exec(code, namespace)
    return recorder.elements
