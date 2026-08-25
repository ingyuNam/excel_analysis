"""업로드된 표를 분석 가능한 형태로 정규화한다.

실무 엑셀은 맨 위에 제목 행이 있거나, 빈 줄이 끼어 있거나, 세로 병합 셀 때문에
칸이 비어 있는 경우가 많다. 그대로 읽으면 헤더가 `Unnamed: 1`로 잡히므로
실제 헤더 행을 추정한 뒤 잘라낸다.
"""

import re

import pandas as pd

MAX_HEADER_SCAN = 12  # 헤더를 찾기 위해 훑어볼 상단 행 수
MERGED_FILL_THRESHOLD = 0.6  # 이 비율 미만으로 채워진 열은 병합 셀로 간주


def read_raw(uploaded_file) -> pd.DataFrame:
    """헤더 추정 없이 원본 격자를 그대로 읽는다. 완전히 빈 행/열만 걷어낸다."""
    uploaded_file.seek(0)
    if uploaded_file.name.endswith(".csv"):
        raw = pd.read_csv(uploaded_file, header=None, dtype=object)
    else:
        raw = pd.read_excel(uploaded_file, header=None, dtype=object)
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    return raw.reset_index(drop=True)


def _is_texty(value) -> bool:
    """헤더다운 값인가. 숫자나 빈 칸은 헤더로 보지 않는다."""
    if value is None or pd.isna(value):
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text.replace(",", ""))
        return False
    except ValueError:
        return True


def detect_header_row(raw: pd.DataFrame, max_scan: int = MAX_HEADER_SCAN) -> int:
    """제목·빈 줄이 앞에 붙은 표에서 실제 헤더 행 위치를 추정한다.

    넓게 채워져 있고, 문자 위주이며, 값이 겹치지 않고,
    아래로 데이터가 이어지는 행일수록 헤더일 가능성이 높다고 본다.
    """
    if raw.empty:
        return 0

    n_cols = max(raw.shape[1], 1)
    best_row, best_score = 0, float("-inf")

    for i in range(min(max_scan, len(raw))):
        row = raw.iloc[i]
        filled = int(row.notna().sum())
        if filled < 2:
            continue  # 제목처럼 한 칸만 찬 행은 헤더가 아니다

        texty = sum(_is_texty(v) for v in row)
        unique = len({str(v).strip() for v in row if pd.notna(v)})
        below = raw.iloc[i + 1 : i + 6]
        below_filled = float(below.notna().sum(axis=1).mean()) if len(below) else 0.0

        score = (
            filled / n_cols * 3.0            # 행이 넓게 채워져 있을수록
            + texty / filled * 2.0           # 문자 위주일수록
            + unique / filled                # 값이 서로 다를수록
            + min(below_filled / n_cols, 1)  # 아래에 데이터가 이어질수록
            - i * 0.05                       # 같은 점수면 위쪽 행 우선
        )
        if score > best_score:
            best_score, best_row = score, i

    return best_row


def _clean_column_names(header_row: pd.Series, n_cols: int) -> list[str]:
    """헤더 셀을 컬럼명으로 다듬고 중복은 접미사로 구분한다."""
    names, seen = [], {}
    for j in range(n_cols):
        value = header_row.iloc[j]
        name = "" if pd.isna(value) else re.sub(r"\s+", " ", str(value).strip())
        name = name or f"열{j + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        names.append(name)
    return names


def _fill_merged_cells(df: pd.DataFrame) -> pd.DataFrame:
    """세로 병합 셀 때문에 비어버린 칸을 위쪽 값으로 채운다.

    드문드문 채워진 분류 열(예: 축의금/조의금)만 대상으로 하고,
    원래 값이 드물게 존재하는 열은 건드리지 않는다.
    """
    for col in df.columns:
        series = df[col]
        if series.dtype != object:
            continue
        filled_ratio = series.notna().mean()
        if 0 < filled_ratio < MERGED_FILL_THRESHOLD:
            df[col] = series.ffill()
    return df


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """"500,000" 같은 문자열 숫자를 실제 숫자 컬럼으로 되돌린다.

    값이 있는 칸이 모두 숫자로 해석될 때만 변환한다. 하나라도 아니면 원본을 유지한다.
    """
    for col in df.columns:
        series = df[col]
        if series.dtype != object:
            continue
        cleaned = series.astype(str).str.replace(",", "", regex=False).str.strip()
        has_value = series.notna() & (cleaned != "")
        if not has_value.any():
            continue
        converted = pd.to_numeric(cleaned, errors="coerce")
        if converted[has_value].notna().all():
            df[col] = converted.where(has_value)
    return df


def build_dataframe(
    raw: pd.DataFrame, header_row: int, fill_merged: bool = True
) -> pd.DataFrame:
    """추정된 헤더 행을 기준으로 표를 잘라 분석용 데이터프레임을 만든다."""
    if raw.empty:
        return raw

    header_row = max(0, min(header_row, len(raw) - 1))
    columns = _clean_column_names(raw.iloc[header_row], raw.shape[1])

    body = raw.iloc[header_row + 1 :].reset_index(drop=True)
    body.columns = columns
    body = body.dropna(how="all").dropna(axis=1, how="all")

    if fill_merged:
        body = _fill_merged_cells(body)
    return _coerce_numeric(body).reset_index(drop=True)


def load_dataframe(uploaded_file, header_row: int | None = None,
                   fill_merged: bool = True) -> pd.DataFrame:
    """업로드 파일을 바로 정규화된 데이터프레임으로 읽는다."""
    raw = read_raw(uploaded_file)
    if header_row is None:
        header_row = detect_header_row(raw)
    return build_dataframe(raw, header_row, fill_merged)


def describe_dataframe(df: pd.DataFrame) -> str:
    """LLM 프롬프트에 넣을 데이터프레임 요약 문자열."""
    return (
        f"Columns: {list(df.columns)}\n"
        f"Data Types:\n{df.dtypes}\n"
        f"Head:\n{df.head(3).to_string()}"
    )
