"""차트 축 라벨이 겹치는 것을 렌더링 직전에 보정한다.

생성 코드는 매번 달라져서 프롬프트 지시만으로는 레이아웃이 보장되지 않는다.
모든 차트가 반드시 지나가는 `st.pyplot()` 길목에서 런타임에 손봐 준다.

글자 수 같은 어림짐작 대신 **실제 렌더링 크기를 픽셀로 재서** 판단한다.
한글·영문·숫자가 섞이거나 figure가 작을 때 어림짐작이 빗나가기 때문이다.
"""

import math

from matplotlib.category import StrCategoryLocator
from matplotlib.colors import to_rgba
from matplotlib.patches import Wedge
from matplotlib.ticker import FixedLocator

# 범주형 축이 쓰는 locator. 이 경우에만 눈금을 솎아낼 수 있다.
# 날짜·수치 축은 matplotlib이 이미 간격을 잡아두므로 건드리면 눈금이 엉뚱해진다.
_CATEGORICAL_LOCATORS = (FixedLocator, StrCategoryLocator)

_PAD_PX = 8      # 라벨 사이 최소 여백. 4px면 글자가 서로 닿을 만큼 빠듯하다
_MIN_TICKS = 4   # 이보다 적게 솎아내면 차트를 읽을 수 없다
_ESCALATION = (45, 90)  # 눕히는 각도를 이 순서로 올린다


def _visible_ticks(ax) -> list:
    return [t for t in ax.get_xticklabels() if t.get_text().strip()]


def _label_extent(ax, renderer) -> tuple[float, float]:
    """회전과 무관한 라벨 원본 크기(가장 넓은 폭, 가장 높은 높이)를 픽셀로 잰다."""
    width = height = 0.0
    for tick in _visible_ticks(ax):
        w, h, _ = renderer.get_text_width_height_descent(
            tick.get_text(), tick.get_fontproperties(), False
        )
        width, height = max(width, w), max(height, h)
    return width, height


def _tick_spacing(ax) -> float:
    """이웃한 눈금 사이의 실제 간격(픽셀). 하나뿐이면 무한대로 본다."""
    ticks = ax.get_xticks()
    if len(ticks) < 2:
        return float("inf")
    points = ax.transData.transform([(x, 0) for x in ticks])
    xs = sorted(p[0] for p in points)
    return min(b - a for a, b in zip(xs, xs[1:]))


def _needed_space(rotation: float, width: float, height: float) -> float:
    """이 각도로 눕혔을 때 라벨 하나가 x축에서 차지해야 하는 최소 간격.

    눕힌 글자는 서로 어긋나 지나가므로, 필요한 간격은 글자 폭이 아니라
    '글자 높이 / sin(각도)'가 된다. 90도면 높이만큼만 있으면 된다.
    """
    angle = abs(rotation) % 180
    if angle == 0:
        return width + _PAD_PX
    return height / math.sin(math.radians(angle)) + _PAD_PX


def _can_thin(ax) -> bool:
    return isinstance(ax.xaxis.get_major_locator(), _CATEGORICAL_LOCATORS)


def _thin_ticks(ax, factor: int = 2) -> bool:
    """눈금을 factor 간격으로 솎아낸다. 더 줄일 수 없으면 False."""
    ticks = list(ax.get_xticks())
    labels = [t.get_text() for t in ax.get_xticklabels()]
    if len(ticks) != len(labels) or len(ticks) // factor < _MIN_TICKS:
        return False
    ax.set_xticks(ticks[::factor])
    ax.set_xticklabels(labels[::factor])
    return True


def _set_rotation(ax, angle: float) -> None:
    for tick in ax.get_xticklabels():
        tick.set_rotation(angle)
        # anchor 모드로 오른쪽 끝을 눈금에 붙여야 눕힌 라벨이 서로 밀리지 않는다.
        tick.set_horizontalalignment("right")
        tick.set_rotation_mode("anchor")


def _current_rotation(ax) -> float:
    ticks = _visible_ticks(ax)
    return abs(ticks[0].get_rotation()) % 180 if ticks else 0.0


def _tidy_axis(ax, renderer) -> None:
    """라벨이 실제로 겹칠 때만, 겹치지 않을 때까지 단계적으로 손본다.

    회전 -> 솎아내기 -> 더 큰 회전 순으로 올린다. 이미 충분하면 아무것도 하지 않아
    'Q1~Q4' 같은 짧은 라벨이나 생성 코드가 잡아둔 레이아웃은 그대로 둔다.
    """
    if not _visible_ticks(ax):
        return

    width, height = _label_extent(ax, renderer)
    if width <= 0:
        return

    for _ in range(6):  # 무한 루프 방지
        rotation = _current_rotation(ax)
        if _needed_space(rotation, width, height) <= _tick_spacing(ax):
            return  # 이미 겹치지 않는다

        harder = next((a for a in _ESCALATION if a > rotation), None)
        # 눕히기를 먼저 시도하되, 45도로도 모자라면 솎아낸 뒤 90도로 간다.
        if harder == 45:
            _set_rotation(ax, 45)
        elif _can_thin(ax) and _thin_ticks(ax):
            continue
        elif harder:
            _set_rotation(ax, harder)
        else:
            return  # 더 해볼 수단이 없다


def _luminance(color) -> float:
    """사람 눈이 느끼는 밝기. 초록에 민감하고 파랑에 둔한 가중치를 쓴다."""
    r, g, b = to_rgba(color)[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def _ring_bounds(wedge: Wedge) -> tuple[float, float]:
    """도넛 조각의 안쪽/바깥쪽 반지름. width가 없으면 꽉 찬 원이다."""
    outer = wedge.r
    width = wedge.width if wedge.width else outer
    return outer - width, outer


def _covering_wedge(wedges: list[Wedge], x: float, y: float) -> Wedge | None:
    """이 좌표를 실제로 덮고 있는 조각. 없으면 구멍이나 바깥 여백이다."""
    for wedge in wedges:
        cx, cy = wedge.center
        dx, dy = x - cx, y - cy
        inner, outer = _ring_bounds(wedge)
        if not inner <= math.hypot(dx, dy) <= outer:
            continue
        angle = math.degrees(math.atan2(dy, dx)) % 360
        start, end = wedge.theta1 % 360, wedge.theta2 % 360
        inside = start <= angle <= end if start <= end else angle >= start or angle <= end
        if inside:
            return wedge
    return None


def _tidy_pie(ax) -> None:
    """파이·도넛 차트의 라벨을 읽을 수 있게 만든다.

    두 가지를 고친다.
    1) 위치: autopct 기본값(pctdistance=0.6)이 도넛 구멍 경계와 겹쳐 글자가
       반쯤 잘려 보인다. 고리 한가운데로 옮긴다.
    2) 색: `textprops={'color': 'w'}` 로 흰 글자를 지정하면 조각 위에서는 읽히지만
       구멍이나 차트 바깥의 흰 배경에서는 사라진다. 뒤에 실제로 무엇이 있는지 보고
       대비가 부족할 때만 색을 바꾼다.
    """
    wedges = [p for p in ax.patches if isinstance(p, Wedge)]
    if not wedges:
        return

    inner, outer = _ring_bounds(wedges[0])
    is_donut = inner > 0
    center_x, center_y = wedges[0].center
    ring_mid = (inner + outer) / 2

    for text in ax.texts:
        x, y = text.get_position()
        dx, dy = x - center_x, y - center_y
        distance = math.hypot(dx, dy)

        # 1) 구멍에 걸친 안쪽 라벨을 고리 한가운데로 민다.
        if is_donut and distance < inner + (outer - inner) * 0.2:
            angle = math.atan2(dy, dx)
            x = center_x + math.cos(angle) * ring_mid
            y = center_y + math.sin(angle) * ring_mid
            text.set_position((x, y))

        # 2) 옮긴 위치 기준으로 배경을 다시 판정해 색을 맞춘다.
        wedge = _covering_wedge(wedges, x, y)
        if wedge is not None:
            background = wedge.get_facecolor()
        else:
            background = ax.get_facecolor()
            if to_rgba(background)[3] == 0:
                background = ax.figure.get_facecolor()

        if abs(_luminance(text.get_color()) - _luminance(background)) < 0.35:
            text.set_color("black" if _luminance(background) > 0.5 else "white")


def tidy_figure(fig) -> None:
    """figure의 모든 축 라벨을 읽을 수 있게 보정한다. 실패해도 차트는 그대로 살린다."""
    try:
        # 자동 눈금은 그리기 전까지 라벨 문자열과 위치가 확정되지 않는다.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return

    for ax in fig.axes:
        try:
            _tidy_pie(ax)
            _tidy_axis(ax, renderer)
        except Exception:
            continue  # 축 하나가 특이해도 나머지는 보정한다

    try:
        # 눕힌 라벨이 잘리지 않도록 여백을 다시 잡는다.
        fig.tight_layout()
    except Exception:
        pass
