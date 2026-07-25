from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
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
def get_vision_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        google_api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        temperature=temperature,
        max_output_tokens=500,
    )