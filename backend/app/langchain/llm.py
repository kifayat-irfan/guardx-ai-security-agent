"""Local LLM abstraction — Ollama via LangChain, optional by design.

- No API key required. Model name, base URL, and timeout are configurable.
- Nothing here requires a running LLM: ``is_available()`` probes the
  Ollama server, and ``get_llm`` raises LLMUnavailableError with a clear
  message instead of hanging or crashing.
- The default model is intentionally small (CPU-friendly); the production
  choice is still open.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


def _sanitize_no_proxy() -> None:
    """Remove bracketed IPv6 tokens from no_proxy in this process.

    VM quirk (documented): entries like ``[::1]`` make httpx raise
    ``InvalidURL: Invalid port`` when the ``ollama`` package builds its
    default client at import time. Localhost entries stay intact.
    """
    for key in ("no_proxy", "NO_PROXY"):
        val = os.environ.get(key)
        if not val:
            continue
        cleaned = ",".join(
            tok for tok in val.split(",")
            if not re.fullmatch(r"\[.*\]", tok.strip())
        )
        os.environ[key] = cleaned


class LLMUnavailableError(RuntimeError):
    """Raised when no local LLM is reachable."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "ollama"
    model: str = "llama3.2:1b"  # small default; CPU-friendly
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 30.0
    temperature: float = 0.0


_lock = threading.Lock()
_llm = None
_llm_config: LLMConfig | None = None


def get_llm_config() -> LLMConfig:
    from app.core.config import get_settings

    s = get_settings()
    return LLMConfig(
        provider=getattr(s, "llm_provider", "ollama"),
        model=getattr(s, "llm_model", "llama3.2:1b"),
        base_url=getattr(s, "llm_base_url", "http://localhost:11434"),
        timeout_seconds=float(getattr(s, "llm_timeout_seconds", 30.0)),
    )


def is_available(config: LLMConfig | None = None) -> bool:
    """Probe the Ollama server without loading anything."""
    config = config or get_llm_config()
    if config.provider != "ollama":
        return False
    try:
        import httpx

        # trust_env=False: bypass the egress proxy for localhost (Phase 1 lesson)
        with httpx.Client(trust_env=False, timeout=3.0) as client:
            resp = client.get(f"{config.base_url}/api/tags")
        return resp.status_code == 200
    except Exception:  # noqa: BLE001 - unavailable is a normal state
        return False


def get_llm(config: LLMConfig | None = None):
    """Return the shared Ollama LLM instance, or raise LLMUnavailableError."""
    global _llm, _llm_config
    config = config or get_llm_config()
    with _lock:
        if _llm is None or _llm_config != config:
            if not is_available(config):
                raise LLMUnavailableError(
                    f"local LLM unavailable at {config.base_url} "
                    f"(model '{config.model}'). Start Ollama or adjust "
                    "llm_* settings; RAG retrieval works without it."
                )
            _sanitize_no_proxy()
            from langchain_ollama import OllamaLLM

            _llm = OllamaLLM(
                model=config.model,
                base_url=config.base_url,
                temperature=config.temperature,
                timeout=config.timeout_seconds,
            )
            _llm_config = config
            logger.info("local LLM ready: %s @ %s", config.model, config.base_url)
        return _llm
