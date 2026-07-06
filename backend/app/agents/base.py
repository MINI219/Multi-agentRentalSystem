"""LLM initialization — shared by all agents.

Returns a ChatOpenAI instance configured for DeepSeek API with tool-calling
support enabled.
"""

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm() -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for DeepSeek API.

    DeepSeek's API is OpenAI-compatible and supports tool/function calling.
    """
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=0.3,
    )
