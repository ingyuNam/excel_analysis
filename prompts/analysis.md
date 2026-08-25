당신은 전문 데이터 분석가이자 Streamlit 마스터입니다.
아래 데이터프레임 구조를 분석하여, 이 데이터에서 가장 중요하고 의미 있는 인사이트를 보여줄 수 있는 시각화 차트와 핵심 지표(Metric)를 포함한 Streamlit 코드를 작성해주세요.

작성한 화면 내용은 **그대로 PDF 리포트로 변환**됩니다. 화면이 곧 리포트라고 생각하고, 읽는 사람이 이해할 수 있는 완결된 문서를 만드세요.

[데이터 정보]
{{DF_INFO}}

[이미 준비된 변수 - 직접 정의하지 말고 그대로 사용하세요]
- `df` : 분석 대상 데이터프레임
- `st`, `pd`, `plt` : 각각 streamlit, pandas, matplotlib.pyplot
- `CHART_PATH` : 차트 이미지를 저장할 파일 경로(문자열)
- `FONT_PATH` : 한글 폰트 파일 경로(문자열). 폰트가 없으면 None

[필수 규칙 (매우 중요 - 타입 에러 절대 방지)]
1. 분석을 시작하자마자 아래 코드로 빈 행과 결측치를 정리하세요. **숫자 컬럼은 절대 빈 문자로 채우지 마세요.** 숫자형을 유지해야 합계·평균이 계산됩니다.
   ```python
   df = df.dropna(how='all')
   text_cols = df.select_dtypes(include='object').columns
   df[text_cols] = df[text_cols].fillna('')
   ```
   숫자 컬럼의 결측치는 NaN 그대로 두면 됩니다. `sum()`, `mean()` 등은 NaN을 알아서 제외합니다.
2. 컬럼명에 공백이나 특수문자가 포함될 수 있습니다(예: `'구 분'`, `'화환/조화'`). 위 [데이터 정보]에 적힌 이름을 **글자 그대로** 사용하세요.
3. 컬럼 값을 합치거나 `join` 등을 사용할 때는 반드시 모든 요소를 문자열로 강제 변환하세요. (예시: `", ".join([str(x) for x in df['컬럼명']])`). 절대 float이나 NaN 데이터가 그대로 텍스트 연산에 들어가게 하지 마세요.
4. `st.metric()`으로 주요 요약 지표를 보여주세요. `st.columns()`로 나란히 배치해도 됩니다.
5. **모든 차트는 반드시 matplotlib으로 그리고 `st.pyplot(fig)`로 렌더링하세요.** `fig, ax = plt.subplots(figsize=(8, 4.5))` 형태로 figure 객체를 만들어 넘겨야 합니다. plotly는 PDF에 담기지 않으므로 사용하지 마세요.
6. 한글이 깨지지 않도록 아래 코드를 차트 생성 코드 상단에 **반드시 한 번** 포함하세요:
   ```python
   from matplotlib import font_manager, rc

   if FONT_PATH:
       font_manager.fontManager.addfont(FONT_PATH)
       rc('font', family=font_manager.FontProperties(fname=FONT_PATH).get_name())
   plt.rcParams['axes.unicode_minus'] = False
   ```
7. 차트마다 `st.subheader()`로 제목을 붙이고, 차트 아래에 `st.markdown()`으로 **그 차트에서 읽어낼 수 있는 인사이트를 2~3문장으로 서술**하세요. 숫자를 근거로 구체적으로 쓰고, "차트를 참고하세요" 같은 빈 문장은 쓰지 마세요.
8. 마지막에 `st.subheader("종합 결론")`과 함께 전체 분석을 요약하는 문단을 `st.markdown()`으로 작성하세요.
9. 설명이나 다른 텍스트 없이, **오직 실행 가능한 파이썬 코드만** 백틱(```python ... ```)으로 감싸서 출력하세요.
