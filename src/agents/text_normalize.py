import unicodedata

_STRIP_CHARS = "!¡.,?¿;: \t\n"

CONFIRM_WORDS: frozenset[str] = frozenset({
    "si", "dale", "ok", "okey", "confirmo", "confirmar", "de una",
    "obvio", "claro", "bueno", "bien", "perfecto", "listo",
})

CANCEL_WORDS: frozenset[str] = frozenset({
    "cancelar", "cancela", "cancelo", "anular", "anula",
    "no quiero", "descartar", "borrar pedido",
    "no", "nop", "nel", "nope",
})


def normalize_text(msg: str) -> str:
    """Lowercase, strip edge punctuation/whitespace, collapse internal whitespace,
    and strip accents so e.g. "Sí." and "si" compare equal."""
    text = msg.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    text = text.strip(_STRIP_CHARS)
    return text


def is_confirm(msg: str) -> bool:
    return normalize_text(msg) in CONFIRM_WORDS


def is_cancel(msg: str) -> bool:
    return normalize_text(msg) in CANCEL_WORDS
