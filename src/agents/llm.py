from typing import Type, TypeVar
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from src.config import get_settings

settings = get_settings()

T = TypeVar("T", bound=BaseModel)


def _build_gemini(temperature: float = 0.7, max_tokens: int = 1000) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        google_api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def get_chat_llm(temperature: float = 0.7):
    """LLM for free-text conversation responses."""
    llm = _build_gemini(temperature=temperature, max_tokens=1000)
    return llm.with_retry(stop_after_attempt=2, wait_exponential_jitter=False)


def get_structured_llm(schema: Type[T], temperature: float = 0):
    """LLM with guaranteed structured JSON output matching the given Pydantic schema.

    Uses Gemini's native controlled generation — the model cannot return
    anything except valid JSON conforming to the schema.
    """
    structured = _build_gemini(temperature=temperature, max_tokens=2000).with_structured_output(schema)
    return structured.with_retry(stop_after_attempt=2, wait_exponential_jitter=False)


def get_vision_llm(temperature: float = 0.2):
    """Vision-capable LLM for receipt/image analysis."""
    llm = _build_gemini(temperature=temperature, max_tokens=500)
    return llm.with_retry(stop_after_attempt=2, wait_exponential_jitter=False)
