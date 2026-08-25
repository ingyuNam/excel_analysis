"""생성된 분석 코드가 화면에 렌더링한 내용을 그대로 기록한다.

`st`를 이 프록시로 바꿔 넣으면 Streamlit에 정상적으로 그리면서
동시에 PDF용 구조를 순서대로 수집한다. 모델의 협조가 필요 없는 방식이다.
"""

import io

import pandas as pd

# 텍스트로 기록할 메서드 → 제목 레벨(0이면 본문)
_TEXT_METHODS = {
    "title": 1,
    "header": 2,
    "subheader": 3,
    "markdown": 0,
    "text": 0,
    "caption": 0,
    "write": 0,
}


def _fig_to_png(fig) -> bytes | None:
    """matplotlib / plotly figure를 PNG 바이트로. 실패하면 None."""
    if hasattr(fig, "savefig"):  # matplotlib
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        return buf.getvalue()
    if hasattr(fig, "to_image"):  # plotly
        try:
            return fig.to_image(format="png", scale=2)
        except Exception:
            # kaleido 미설치 등. 화면 렌더링은 그대로 두고 PDF에서만 건너뛴다.
            return None
    return None


class ReportRecorder:
    """수집된 요소 목록을 들고 있는 저장소."""

    def __init__(self) -> None:
        self.elements: list[dict] = []

    def add(self, **element) -> None:
        self.elements.append(element)

    def add_object(self, obj) -> None:
        """st.write(...) 처럼 타입이 정해지지 않은 인자를 종류에 맞게 기록."""
        if isinstance(obj, pd.DataFrame):
            self.add(type="table", df=obj)
        elif isinstance(obj, pd.Series):
            self.add(type="table", df=obj.to_frame())
        elif hasattr(obj, "savefig") or hasattr(obj, "to_image"):
            png = _fig_to_png(obj)
            if png:
                self.add(type="image", png=png)
        elif isinstance(obj, str):
            self.add(type="text", level=0, text=obj)


class _RecordingProxy:
    """실제 Streamlit 객체에 위임하면서 렌더링 내용을 기록하는 래퍼."""

    def __init__(self, target, recorder: ReportRecorder) -> None:
        self._target = target
        self._recorder = recorder

    def __getattr__(self, name):
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            self._record(name, args, kwargs)
            return self._wrap_result(name, attr(*args, **kwargs))

        return wrapped

    # 컨텍스트 매니저(`with col:`, `with st.expander(...)`)를 그대로 지원
    def __enter__(self):
        self._target.__enter__()
        return self

    def __exit__(self, *exc):
        return self._target.__exit__(*exc)

    def _wrap_result(self, name, result):
        """columns/tabs/container처럼 하위 렌더링 대상을 돌려주는 경우도 감싼다."""
        if name in ("columns", "tabs"):
            return [_RecordingProxy(item, self._recorder) for item in result]
        if name in ("container", "expander", "sidebar", "empty", "form"):
            return _RecordingProxy(result, self._recorder)
        return result

    def _record(self, name, args, kwargs) -> None:
        rec = self._recorder

        if name in _TEXT_METHODS:
            level = _TEXT_METHODS[name]
            if args and isinstance(args[0], str):
                rec.add(type="text", level=level, text=args[0])
            elif args:
                rec.add_object(args[0])

        elif name == "metric":
            label = kwargs.get("label", args[0] if args else "")
            value = kwargs.get("value", args[1] if len(args) > 1 else "")
            delta = kwargs.get("delta", args[2] if len(args) > 2 else None)
            rec.add(type="metric", label=str(label), value=str(value),
                    delta=None if delta is None else str(delta))

        elif name in ("dataframe", "table"):
            if args and isinstance(args[0], (pd.DataFrame, pd.Series)):
                rec.add_object(args[0])

        elif name in ("plotly_chart", "pyplot", "altair_chart", "image"):
            if args:
                png = _fig_to_png(args[0])
                if png:
                    rec.add(type="image", png=png)
                elif name == "plotly_chart":
                    rec.add(type="missing_chart")

        elif name == "divider":
            rec.add(type="divider")


def recording_streamlit(st_module, recorder: ReportRecorder) -> _RecordingProxy:
    return _RecordingProxy(st_module, recorder)
