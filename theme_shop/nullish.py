"""JavaScript's nullish coalescing for the payload fields the SPA reads with ``??``."""
from typing import Any


def present_or(value: Any, fallback: Any) -> Any:
    """``value ?? fallback``: ``fallback`` only when ``value`` is ``None``."""
    return fallback if value is None else value
