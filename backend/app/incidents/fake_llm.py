"""Deterministic fake LLM for graph tests — no Ollama required.

FakeAnalysisLLM parses the chunk IDs out of the prompt it receives (they are
rendered as ``[chunk_id: ...]`` by format_policy_context) and builds a
scenario response:

- "valid":        well-formed JSON citing the first two retrieved chunk IDs
- "fabricated":   well-formed JSON citing a chunk that was NOT retrieved
- "malformed":    not JSON at all
- "bad_severity": JSON with an invalid severity value
- "bad_confidence": JSON with confidence outside 0-1
"""
from __future__ import annotations

import json
import re

_CHUNK_RE = re.compile(r"\[chunk_id:\s*([^\]]+)\]")


class FakeAnalysisLLM:
    def __init__(self, scenario: str = "valid"):
        if scenario not in (
            "valid", "fabricated", "malformed",
            "bad_severity", "bad_confidence",
        ):
            raise ValueError(f"unknown scenario: {scenario}")
        self.scenario = scenario
        self.calls: list[str] = []

    def _prompt_text(self, prompt_value) -> str:
        if hasattr(prompt_value, "to_string"):
            return prompt_value.to_string()
        if hasattr(prompt_value, "messages"):
            return "\n".join(
                f"{m.type}: {m.content}" for m in prompt_value.messages
            )
        return str(prompt_value)

    def invoke(self, prompt_value) -> str:
        text = self._prompt_text(prompt_value)
        self.calls.append(text)
        chunk_ids = _CHUNK_RE.findall(text)

        if self.scenario == "malformed":
            return "I cannot comply with that request right now."
        if self.scenario == "fabricated":
            cited = ["fake-policy#rules"]
        else:
            cited = chunk_ids[:2]

        payload = {
            "summary": "A person entered the restricted server room.",
            "severity": "HIGH",
            "recommended_action": (
                "Notify security personnel and review the event."
            ),
            "cited_policy_chunk_ids": cited,
            "reasoning": (
                "Fact: zone_enter detected. Policy: unauthorized presence "
                "in a restricted zone is HIGH severity."
            ),
            "confidence": 0.91,
        }
        if self.scenario == "bad_severity":
            payload["severity"] = "EXTREME"
        if self.scenario == "bad_confidence":
            payload["confidence"] = 2.5
        return json.dumps(payload)
