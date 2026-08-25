import threading
import traceback

import matplotlib

matplotlib.use("Agg")  # 헤드리스 서버에서 GUI 백엔드를 잡지 않도록 pyplot 임포트 전에 고정

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from core.report_recorder import ReportRecorder, recording_streamlit  # noqa: E402

# exec에 넘길 코드의 가상 파일명. 트레이스백에서 생성 코드 프레임만 골라낼 때 쓴다.
_FILENAME = "<analysis>"

# Streamlit은 브라우저 세션마다 별도 스레드로 스크립트를 돌리는데, pyplot은
# 전역 figure 매니저를 쓰고 스레드 안전하지 않다. 두 사람이 동시에 차트를 그리면
# figure가 섞이거나 엉뚱한 축에 그려지므로, 생성 코드 실행 구간은 직렬화한다.
# 느린 구간(Gemini 호출)은 이 락 바깥이라 대기는 짧다.
_EXEC_LOCK = threading.Lock()


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


def _close_new_figures(before: set[int]) -> None:
    """이번 실행에서 새로 만들어진 figure만 닫는다.

    plt.subplots()로 만든 figure는 pyplot이 계속 참조를 들고 있어 스스로 사라지지
    않는다. 리런마다 쌓이면 메모리 한도를 넘겨 앱 전체가 죽는다.
    plt.close("all")은 다른 세션 것까지 닫을 수 있어 쓰지 않는다.
    """
    for num in set(plt.get_fignums()) - before:
        plt.close(num)


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
    # rc_context: 생성 코드가 건드리는 rcParams(폰트, unicode_minus)를 이 실행에만
    # 가두고 빠져나올 때 되돌린다. 전역 설정이라 그냥 두면 다른 세션에 새어 나간다.
    with _EXEC_LOCK, plt.rc_context():
        before = set(plt.get_fignums())
        try:
            exec(compiled, namespace)
        except Exception as exc:
            lineno = _failing_lineno(exc)
            lines = code.splitlines()
            source = lines[lineno - 1].strip() if lineno and lineno <= len(lines) else ""
            # 터지기 전까지 기록된 내용은 살려 보낸다. 앞부분만으로도 PDF는 나온다.
            raise AnalysisCodeError(exc, lineno, source, recorder.elements) from exc
        finally:
            _close_new_figures(before)
    return recorder.elements
