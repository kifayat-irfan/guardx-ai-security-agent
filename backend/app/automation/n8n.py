"""Minimal n8n webhook client (Phase 9).

- Disabled by default; zero network traffic unless enabled + configured.
- Short timeout, trust_env=False (this VM's no_proxy breaks httpx parsing).
- Failures are returned as data, never raised into the incident path.
- The shared secret is sent as a header but NEVER logged.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.automation.schemas import N8nIncidentPayload

logger = logging.getLogger(__name__)

SECRET_HEADER = "X-GuardX-Webhook-Secret"


class N8nResult:
    def __init__(self, ok: bool, status: str,
                 http_status: int | None = None,
                 detail: str | None = None):
        self.ok = ok
        self.status = status  # sent | disabled | not_configured | failed
        self.http_status = http_status
        self.detail = detail


class N8nClient:
    def __init__(self, webhook_url: str = "", secret: str = "",
                 timeout_seconds: float = 5.0,
                 transport: httpx.BaseTransport | None = None):
        self.webhook_url = webhook_url
        self._secret = secret
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url.strip())

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._secret:
            headers[SECRET_HEADER] = self._secret
        return headers

    def _client(self) -> httpx.Client:
        # trust_env=False: bracketed IPv6 tokens in this VM's no_proxy
        # break httpx proxy parsing (Phase 1 lesson).
        return httpx.Client(
            timeout=self.timeout_seconds,
            trust_env=False,
            transport=self._transport,
        )

    def send(self, payload: N8nIncidentPayload) -> N8nResult:
        """POST the payload. Never raises — failures become N8nResult."""
        if not self.configured:
            return N8nResult(False, "not_configured",
                             detail="N8N_WEBHOOK_URL is empty")

        body = payload.model_dump(mode="json")
        t0 = time.perf_counter()
        try:
            with self._client() as client:
                resp = client.post(
                    self.webhook_url, json=body, headers=self._headers()
                )
            ms = (time.perf_counter() - t0) * 1000
            if 200 <= resp.status_code < 300:
                logger.info(
                    "n8n webhook delivered: event=%s status=%s http=%s %.0fms",
                    payload.event_id, payload.status, resp.status_code, ms,
                )
                return N8nResult(True, "sent", http_status=resp.status_code)
            # Never log the secret or the full body; the event id suffices.
            logger.warning(
                "n8n webhook HTTP %s: event=%s (no secret logged)",
                resp.status_code, payload.event_id,
            )
            return N8nResult(
                False, "failed", http_status=resp.status_code,
                detail=f"HTTP {resp.status_code}",
            )
        except httpx.TimeoutException:
            logger.warning(
                "n8n webhook timeout after %.1fs: event=%s",
                self.timeout_seconds, payload.event_id,
            )
            return N8nResult(False, "failed", detail="timeout")
        except httpx.ConnectError as exc:
            logger.warning(
                "n8n webhook unreachable: event=%s err=%s",
                payload.event_id, str(exc)[:120],
            )
            return N8nResult(False, "failed", detail="unreachable")
        except Exception as exc:  # noqa: BLE001 - failure isolation
            logger.warning(
                "n8n webhook error: event=%s err=%s",
                payload.event_id, str(exc)[:120],
            )
            return N8nResult(False, "failed", detail="error")

    def check_reachable(self, timeout: float = 3.0) -> str:
        """Lightweight reachability probe: 'reachable' | 'unreachable'.

        n8n webhooks only accept POST, so a GET is expected to 404/405 —
        a completed handshake still proves the host is reachable.
        Never raises.
        """
        if not self.configured:
            return "not_configured"
        try:
            with httpx.Client(timeout=timeout, trust_env=False,
                              transport=self._transport) as client:
                client.get(self.webhook_url)
            return "reachable"
        except Exception:  # noqa: BLE001 - health must not raise
            return "unreachable"
