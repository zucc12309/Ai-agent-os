from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "headers",
    "auth",
)

MAX_STRING_LENGTH = 4000
MAX_SEQUENCE_LENGTH = 20


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_payload(value: Any) -> Any:
    """Return a JSON-serializable payload with sensitive data obscured."""

    if value is None:
        return None

    if isinstance(value, str):
        if len(value) <= MAX_STRING_LENGTH:
            return value
        return f"{value[: MAX_STRING_LENGTH - 1]}…"

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _is_sensitive_key(key):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_payload(item)
        return redacted

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        items = [redact_payload(item) for item in value[:MAX_SEQUENCE_LENGTH]]
        if len(value) > MAX_SEQUENCE_LENGTH:
            items.append(f"[truncated {len(value) - MAX_SEQUENCE_LENGTH} items]")
        return items

    return value


def redact_error_message(value: str | None) -> str | None:
    if value is None:
        return None

    lowered = value.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if len(value) <= MAX_STRING_LENGTH:
        return value
    return f"{value[: MAX_STRING_LENGTH - 1]}…"
