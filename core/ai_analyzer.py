from google import genai

from config import GENAI_API_KEY, GENAI_MODEL, PROMPT_DIR


def build_prompt(df_info: str) -> str:
    """프롬프트 템플릿에 데이터 요약을 끼워 넣는다.

    템플릿에 코드 예시(중괄호)가 들어가도 깨지지 않도록 format 대신 replace를 쓴다.
    """
    template = (PROMPT_DIR / "analysis.md").read_text(encoding="utf-8")
    return template.replace("{{DF_INFO}}", df_info)


def extract_code(text: str) -> str:
    """응답에서 파이썬 코드 블록만 뽑아낸다."""
    if "```python" in text:
        return text.split("```python")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()


def generate_analysis_code(df_info: str) -> str:
    """Gemini에 분석 코드 생성을 요청하고 실행 가능한 코드만 반환한다."""
    client = genai.Client(api_key=GENAI_API_KEY)
    response = client.models.generate_content(
        model=GENAI_MODEL, contents=[build_prompt(df_info)]
    )
    return extract_code(response.text)
