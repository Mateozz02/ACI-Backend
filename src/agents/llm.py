from typing import Optional
from langchain_openai import ChatOpenAI
from src.config import get_settings

settings = get_settings()


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.opencode_base_url,
        api_key=settings.opencode_api_key,
        model=model or settings.model_name,
        temperature=temperature,
        max_tokens=1000,
    )
