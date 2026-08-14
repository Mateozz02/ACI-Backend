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
    )


def get_chat_llm(temperature: float = 0.7) -> ChatGoogleGenerativeAI:
    """LLM for free-text conversation responses."""
    return _build_gemini(temperature=temperature, max_tokens=1000)


def get_structured_llm(schema: Type[T], temperature: float = 0) -> T:
    """LLM with guaranteed structured JSON output matching the given Pydantic schema.

    Uses Gemini's native controlled generation — the model cannot return
    anything except valid JSON conforming to the schema.
    """
    return _build_gemini(temperature=temperature, max_tokens=2000).with_structured_output(schema)


def get_vision_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    """Vision-capable LLM for receipt/image analysis."""
    return _build_gemini(temperature=temperature, max_tokens=500)
