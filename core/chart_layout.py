"""차트 축 라벨이 겹치는 것을 렌더링 직전에 보정한다.

생성 코드는 매번 달라져서 프롬프트 지시만으로는 레이아웃이 보장되지 않는다.
모든 차트가 반드시 지나가는 `st.pyplot()` 길목에서 런타임에 손봐 준다.
'2028-03-11' 같은 긴 라벨이 가로로 붙어 뭉개지는 경우가 대표적이다.
"""

from matplotlib.category import StrCategoryLocator
from matplotlib.ticker import FixedLocator

# 범주형 축이 쓰는 두 locator. 이 경우에만 눈금을 솎아낸다.
_CATEGORICAL_LOCATORS = (FixedLocator, StrCategoryLocator)

# 이보다 눈금이 많으면 솎아낸다. 8인치 폭 기준 이 정도가 읽을 수 있는 한계.
_MAX_TICKS = 12
# 이보다 긴 라벨이 하나라도 있으면 회전시킨다. 'Q1' 같은 짧은 건 눕히지 않는다.
_LONG_LABEL = 5
# 라벨이 짧아도 이 개수를 넘으면 회전시킨다.
_CROWDED = 8


def _tick_texts(ax) -> list[str]:
    return [t.get_text() for t in ax.get_xticklabels()]


def _already_rotated(ax) -> bool:
    """생성 코드가 이미 회전을 넣었으면 건드리지 않는다."""
    return any(t.get_rotation() % 180 != 0 for t in ax.get_xticklabels())


def _thin_ticks(ax, labels: list[str]) -> list[str]:
    """눈금이 너무 많으면 일정 간격으로 솎아낸다.

    범주형 축일 때만 손댄다. 날짜·수치 축은 matplotlib이 이미 적절히 간격을
    잡아두므로 억지로 줄이면 오히려 눈금이 엉뚱한 위치에 찍힌다.
    """
    if len(labels) <= _MAX_TICKS:
        return labels
    if not isinstance(ax.xaxis.get_major_locator(), _CATEGORICAL_LOCATORS):
        return labels

    ticks = ax.get_xticks()
    if len(ticks) != len(labels):
        return labels

    step = len(labels) // _MAX_TICKS + 1
    ax.set_xticks(ticks[::step])
    ax.set_xticklabels(labels[::step])
    return labels[::step]


def _tidy_axis(ax) -> None:
    labels = [text for text in _tick_texts(ax) if text]
    if not labels or _already_rotated(ax):
        return

    labels = _thin_ticks(ax, _tick_texts(ax)) or labels
    visible = [text for text in labels if text]
    if not visible:
        return

    if max(len(text) for text in visible) > _LONG_LABEL or len(visible) > _CROWDED:
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
            # anchor 모드로 오른쪽 끝을 눈금에 붙여야 눕힌 라벨이 서로 밀리지 않는다.
            tick.set_horizontalalignment("right")
            tick.set_rotation_mode("anchor")


def tidy_figure(fig) -> None:
    """figure의 모든 축 라벨을 읽을 수 있게 보정한다. 실패해도 차트는 그대로 살린다."""
    try:
        # 자동 눈금은 그리기 전까지 라벨 문자열이 비어 있어 판단할 수 없다.
        fig.canvas.draw()
    except Exception:
        return

    for ax in fig.axes:
        try:
            _tidy_axis(ax)
        except Exception:
            continue  # 축 하나가 특이해도 나머지는 보정한다

    try:
        # 눕힌 라벨이 잘리지 않도록 여백을 다시 잡는다.
        fig.tight_layout()
    except Exception:
        pass
