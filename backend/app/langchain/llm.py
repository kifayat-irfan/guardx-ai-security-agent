"""LLM abstraction — Ollama (local) or SenseNova (API), optional by design.

- No LLM is required to run GuardX: ``is_available()`` probes the
  provider, and ``get_llm`` raises LLMUnavailableError with a clear
  message instead of hanging or crashing.
- Select the provider with ``LLM_PROVIDER``: ``ollama`` (default) or
  ``sensenova``. The SenseNova key comes from ``SENSENOVA_API_KEY``
  (gitignored ``.env``); it is never printed, logged, or committed.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field

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
    # SenseNova (post-Phase-10): key never logged — repr=False.
    api_key: str = field(default="", repr=False)
    max_tokens: int = 1024
    retries: int = 1


_lock = threading.Lock()
_llm = None
_llm_config: LLMConfig | None = None


def get_llm_config() -> LLMConfig:
    from app.core.config import get_settings

    s = get_settings()
    provider = getattr(s, "llm_provider", "ollama")
    # provider-specific defaults: a sensenova provider without an explicit
    # model/base_url falls back to the token-plan chat endpoint + flash-lite
    from app.langchain.sensenova import DEFAULT_BASE_URL, DEFAULT_MODEL

    model = getattr(s, "llm_model", "")
    base_url = getattr(s, "llm_base_url", "")
    if provider == "sensenova":
        model = model or DEFAULT_MODEL
        base_url = base_url or DEFAULT_BASE_URL
    return LLMConfig(
        provider=provider,
        model=model or "llama3.2:1b",
        base_url=base_url or "http://localhost:11434",
        timeout_seconds=float(getattr(s, "llm_timeout_seconds", 30.0)),
        api_key=getattr(s, "sensenova_api_key", "") or "",
        max_tokens=int(getattr(s, "sensenova_max_tokens", 1024)),
        retries=int(getattr(s, "sensenova_retries", 1)),
    )


def _has_sensenova_key(config: LLMConfig) -> bool:
    return bool(config.api_key and config.api_key.strip())


def is_available(config: LLMConfig | None = None) -> bool:
    """Probe the LLM provider without loading anything or spending quota.

    SenseNova: key presence is the local check — no network call, so health
    checks never burn the limited API allowance. Auth itself is verified
    lazily on the first real invocation.
    """
    config = config or get_llm_config()
    if config.provider == "sensenova":
        return _has_sensenova_key(config)
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
    """Return the shared LLM instance, or raise LLMUnavailableError."""
    global _llm, _llm_config
    config = config or get_llm_config()
    with _lock:
        if _llm is None or _llm_config != config:
            if config.provider == "sensenova":
                if not _has_sensenova_key(config):
                    raise LLMUnavailableError(
                        "sensenova LLM selected but SENSENOVA_API_KEY is "
                        "not set. Add it to the gitignored .env; RAG "
                        "retrieval works without it."
                    )
                _sanitize_no_proxy()
                from app.langchain.sensenova import SenseNovaChatModel

                _llm = SenseNovaChatModel(
                    model_name=config.model,
                    api_key=config.api_key,
                    base_url=config.base_url,
                    timeout_seconds=config.timeout_seconds,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    retries=config.retries,
                )
                _llm_config = config
                logger.info("sensenova LLM ready: %s", config.model)
            elif config.provider == "ollama":
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
                logger.info("local LLM ready: %s @ %s", config.model,
                            config.base_url)
            else:
                raise LLMUnavailableError(
                    f"unknown llm_provider '{config.provider}' "
                    "(expected 'ollama' or 'sensenova')"
                )
        return _llm
