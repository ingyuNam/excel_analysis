import traceback

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core.report_recorder import ReportRecorder, recording_streamlit

# exec에 넘길 코드의 가상 파일명. 트레이스백에서 생성 코드 프레임만 골라낼 때 쓴다.
_FILENAME = "<analysis>"


class AnalysisCodeError(Exception):
    """생성된 코드가 실행 중 터졌을 때, 어디서 왜 터졌는지까지 들고 가는 예외.

    모델이 만든 코드는 매번 달라져서 메시지만으로는 원인을 좁힐 수 없다.
    실패한 줄 번호와 소스, 그리고 터지기 전까지 그려진 내용을 함께 실어 보낸다.
    """

    def __init__(self, original: Exception, lineno: int | None, source_line: str,
                 elements: list[dict]):
        self.original = original
        self.lineno = lineno
        self.source_line = source_line
        self.elements = elements
        super().__init__(f"{type(original).__name__}: {original}")


def _failing_lineno(exc: Exception) -> int | None:
    """트레이스백에서 생성 코드 프레임의 줄 번호를 찾는다.

    pandas 내부로 여러 겹 들어간 뒤 터지므로, 가장 마지막 <analysis> 프레임이
    실제로 모델이 쓴 줄이다.
    """
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == _FILENAME:
            return frame.lineno
    return None


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
    # compile로 파일명을 붙여야 트레이스백에서 생성 코드 줄을 식별할 수 있다.
    compiled = compile(code, _FILENAME, "exec")
    try:
        exec(compiled, namespace)
    except Exception as exc:
        lineno = _failing_lineno(exc)
        lines = code.splitlines()
        source = lines[lineno - 1].strip() if lineno and lineno <= len(lines) else ""
        # 터지기 전까지 기록된 내용은 살려 보낸다. 앞부분만으로도 PDF는 나온다.
        raise AnalysisCodeError(exc, lineno, source, recorder.elements) from exc
    return recorder.elements
