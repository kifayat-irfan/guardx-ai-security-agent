"""SenseNova LLM provider — OpenAI-compatible chat completions via LangChain.

Contract (verified against SenseNova public docs + the platform reference):

- base URL: ``https://token.sensenova.ai/v1`` (international platform;
  the China ``token.sensenova.cn`` root uses separate keys)
- endpoint: ``POST {base_url}/v1/chat/completions``
- auth: ``Authorization: Bearer <SENSENOVA_API_KEY>``
- request: OpenAI-style ``{model, messages, temperature, max_tokens,
  response_format}`` — ``response_format: {"type": "json_object"}`` is
  supported by the flash models for strict JSON output.
- response: OpenAI-style ``{"choices": [{"message": {"content": ...}}]}``.
- errors: HTTP status + ``{"error": {"type", "code", "message"}}`` body.
  429 = quota exceeded.

Quota safety (the account allowance is limited):

- no network probing in ``is_available`` — key presence is the local check.
- at most ``retries`` extra attempts, only for network/5xx/timeout errors.
- 401/403 (dead key) and 429 (quota) fail fast — no retry storm.
- the real API is never touched by unit tests (httpx MockTransport only).

Failure semantics feed the existing LangGraph statuses:

- missing key              -> LLMUnavailableError (llm_unavailable)
- 401/403/429/timeout/5xx  -> SenseNovaAPIError (analysis_failed, honest)
- malformed envelope/output -> SenseNovaAPIError (analysis_failed)

GuardX never fabricates an analysis: any of these paths ends in the
existing honest failure statuses, never in a synthetic result.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

#: Default international-platform chat endpoint root
#: (overridable via LLM_BASE_URL). The user's account lives on
#: platform.sensenova.ai — keys are NOT valid on token.sensenova.cn.
DEFAULT_BASE_URL = "https://token.sensenova.ai/v1"

#: Default model for the token plan: 256K context, JSON output support,
#: 1500 calls / 5h — the cheapest safe choice for incident analysis.
DEFAULT_MODEL = "sensenova-6.8-flash-lite"


class SenseNovaAPIError(RuntimeError):
    """A SenseNova request failed. Carries machine-readable failure info.

    ``retryable`` is False for auth failures, quota exhaustion, and
    malformed responses — retrying those only burns quota or time.
    """

    def __init__(self, message: str, *,
                 status_code: int | None = None,
                 retryable: bool = False,
                 error_type: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.error_type = error_type


_ROLE_MAP = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
}


def _to_openai_message(message: BaseMessage) -> dict[str, str]:
    role = _ROLE_MAP.get(message.type, "user")
    content = message.content
    if not isinstance(content, str):
        content = str(content)
    return {"role": role, "content": content}


class SenseNovaChatModel(BaseChatModel):
    """LangChain chat model speaking SenseNova's OpenAI-compatible API.

    Satisfies the same ``.invoke(prompt_value) -> .content`` contract the
    incident workflow's ``analyze_event`` node already uses.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = DEFAULT_MODEL
    api_key: str = Field(repr=False, default="")
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    temperature: float = 0.0
    max_tokens: int = 1024
    retries: int = 1
    http_client: httpx.Client | None = Field(default=None, repr=False,
                                             exclude=True)

    @property
    def _llm_type(self) -> str:
        return "sensenova"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        # never include the key — identifying params may be logged
        return {"model": self.model_name, "base_url": self.base_url}

    def _default_client(self) -> httpx.Client:
        # Per-call client: call volume is tiny (quota-limited account), so
        # connection pooling buys nothing; a fresh client avoids stale state.
        return httpx.Client(timeout=self.timeout_seconds)

    def _auth_headers(self) -> dict[str, str]:
        # Applied per request so the key is attached even when a caller
        # injects their own httpx client (tests).
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [_to_openai_message(m) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # strict JSON object — the workflow validates it against
            # SecurityAnalysis, and the citation guard checks chunk IDs.
            "response_format": {"type": "json_object"},
        }
        if stop:
            payload["stop"] = stop

        body = self._post(payload)
        content = self._extract_content(body)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))]
        )

    # -- HTTP ----------------------------------------------------------

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + "/chat/completions"
        if self.http_client is not None:
            # test-injected client (MockTransport): caller owns its lifecycle
            return self._post_with_retry(self.http_client, url, payload)
        with self._default_client() as client:
            return self._post_with_retry(client, url, payload)

    def _post_with_retry(self, client: httpx.Client, url: str,
                         payload: dict[str, Any]) -> dict[str, Any]:
        attempts = 1 + max(0, self.retries)
        last_error: SenseNovaAPIError | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = client.post(url, json=payload,
                                   headers=self._auth_headers())
            except httpx.TimeoutException as exc:
                last_error = SenseNovaAPIError(
                    f"sensenova request timed out after "
                    f"{self.timeout_seconds}s",
                    retryable=True, error_type="timeout",
                )
                logger.warning("sensenova timeout (attempt %d/%d): %s",
                               attempt, attempts, exc)
            except httpx.HTTPError as exc:
                last_error = SenseNovaAPIError(
                    f"sensenova request failed: {exc}",
                    retryable=True, error_type="network",
                )
                logger.warning("sensenova network error (attempt %d/%d): %s",
                               attempt, attempts, exc)
            else:
                try:
                    return self._handle_response(resp)
                except SenseNovaAPIError as exc:
                    if not exc.retryable:
                        raise
                    last_error = exc
            if attempt < attempts and last_error is not None \
                    and last_error.retryable:
                # single short backoff; never a retry storm
                time.sleep(0.5 * attempt)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        try:
            err = resp.json().get("error") or {}
            detail = err.get("message") or err.get("type") or resp.text
        except Exception:  # noqa: BLE001 - best-effort error detail
            detail = resp.text
        return str(detail)[:300]

    def _handle_response(self, resp: httpx.Response) -> dict[str, Any]:
        code = resp.status_code
        if code == 200:
            try:
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                raise SenseNovaAPIError(
                    f"sensenova returned non-JSON body: {exc}",
                    status_code=code, retryable=False,
                    error_type="malformed_envelope",
                ) from exc
        if code in (401, 403):
            raise SenseNovaAPIError(
                f"sensenova authentication failed (HTTP {code}): "
                f"{self._error_message(resp)}. Check SENSENOVA_API_KEY.",
                status_code=code, retryable=False, error_type="auth",
            )
        if code == 429:
            raise SenseNovaAPIError(
                f"sensenova quota exceeded (HTTP 429): "
                f"{self._error_message(resp)}. Not retrying.",
                status_code=code, retryable=False, error_type="quota",
            )
        if 500 <= code < 600:
            logger.warning("sensenova server error HTTP %d: %s",
                           code, self._error_message(resp))
            raise SenseNovaAPIError(
                f"sensenova server error (HTTP {code})",
                status_code=code, retryable=True, error_type="server",
            )
        raise SenseNovaAPIError(
            f"sensenova request rejected (HTTP {code}): "
            f"{self._error_message(resp)}",
            status_code=code, retryable=False, error_type="request",
        )

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        try:
            choices = body["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SenseNovaAPIError(
                f"sensenova response missing choices/message/content: {exc}",
                retryable=False, error_type="malformed_envelope",
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise SenseNovaAPIError(
                "sensenova returned empty content",
                retryable=False, error_type="malformed_envelope",
            )
        return content

    def __repr__(self) -> str:  # never leak the key in a repr
        return (
            f"SenseNovaChatModel(model_name={self.model_name!r}, "
            f"base_url={self.base_url!r}, timeout_seconds={self.timeout_seconds!r})"
        )
