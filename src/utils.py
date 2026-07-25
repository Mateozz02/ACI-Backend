import logging
import re

logger = logging.getLogger("orderflow")


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger("orderflow")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def clean_llm_json(text: str) -> str:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    text = text.strip()
    text = re.sub(r'(\d+)\.(\d{3})', r'\1\2', text)
    text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)
    return text
