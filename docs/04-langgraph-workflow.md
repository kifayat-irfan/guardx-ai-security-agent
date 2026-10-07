# GuardX — LangGraph Incident Workflow (Phase 0)

## Principle

**LangGraph controls the workflow. RAG retrieves policy context. The LLM
reasons.** No node makes a decision from retrieved text alone; the `reason`
node always receives the structured incident *plus* the retrieved policies and
must emit the fixed decision schema.

## State — `IncidentState` (TypedDict)

```python
class RetrievedPolicy(TypedDict):
    chunk_id: str        # e.g. "restricted_area_policy#entry-response"
    title: str
    category: str
    text: str
    score: float

class IncidentDecision(TypedDict):
    incident_type: str
    severity: str            # low | medium | high | critical
    reason: str
    matched_policy: str      # chunk_id from retrieved policies
    recommended_action: str
    report_summary: str

class IncidentState(TypedDict):
    incident_id: str
    camera_id: str
    zone_id: str
    zone_name: str
    track_id: str | None
    incident_type: str       # e.g. "restricted_area_intrusion"
    detected_at: str         # ISO-8601
    snapshot_path: str | None
    hour_local: int          # for after-hours policy relevance
    policies: list[RetrievedPolicy]
    decision: IncidentDecision | None
    report_markdown: str | None
    status: str              # running | completed | error
    error: str | None
```

## Nodes & edges

```
validate ──▶ retrieve_policies ──▶ reason ──▶ build_report ──▶ persist ──▶ notify ──▶ END
   │               │                   │              │             │           │
   └───────────────┴───────────────────┴──────────────┴─────────────┴───────────┘
                        any node raises → error branch → persist_error → notify ──▶ END
```

| Node | Input → Output | What it does |
|------|---------------|--------------|
| `validate` | raw event → validated state | Checks incident exists, zone/camera IDs resolve; stamps `hour_local`; writes `incident_events(step=validate)` |
| `retrieve_policies` | state → state + policies | Builds query from `incident_type + zone_name + hour context`; RAG top-k=3 from ChromaDB; writes retrieved chunk IDs/scores to `incident_events` |
| `reason` | state + policies → decision | LangChain structured-output LLM call. System prompt: *you are a security analyst; use ONLY the incident facts and the provided policy excerpts; cite the chunk you relied on; output exactly the decision schema.* `matched_policy` must be one of the retrieved `chunk_id`s (validated; else retry once, then fall back to `severity=medium` + `matched_policy="none"` and flag). Writes decision to `incident_events` |
| `build_report` | decision → markdown | Renders the incident report (template, no LLM needed): header, facts, severity + reason, matched policy excerpt, recommended action, summary |
| `persist` | report → DB rows | Writes `incident_reports` row; updates `incidents.severity/status`; writes `incident_events(step=persist)` |
| `notify` | persisted → webhook | If `N8N_ENABLED`: POST incident+decision+report to `N8N_WEBHOOK_URL` (timeout 5 s, 2 retries); logs row in `notifications`; emits SSE `notification.sent`. Never raises — failure is recorded, not fatal |

**Conditional edge:** `retrieve_policies` → if zero chunks retrieved, still
proceed to `reason` with `policies=[]`; the prompt then forces
`matched_policy="none"` and a conservative severity. Retrieval failure must
not silently become a confident decision.

## LangChain integration points (Phase 5 → used here in Phase 6)

- `get_chat_model()` factory in `rag/llm.py` (name TBD Phase 5): switches on
  `LLM_PROVIDER` → `ChatOpenAI` / `ChatAnthropic` / `ChatGoogleGenerativeAI` /
  `ChatOllama`. Temperature from env.
- Structured output via `.with_structured_output(IncidentDecisionSchema)`
  (Pydantic model mirroring `IncidentDecision`).
- RAG retriever exposed as a LangChain `Retriever` so the node can also be
  tested standalone.

## Worked example (demo scenario)

1. Person enters "Server Room Door" zone at 22:40 → `ZoneViolationEvent`.
2. `validate`: incident `#a1`, type `restricted_area_intrusion`, hour 22.
3. `retrieve_policies`: query → top chunks: *Restricted Area Policy
   #entry-response* (0.91), *After-Hours Access Policy #scope* (0.84),
   *Incident Reporting Policy #escalation* (0.71).
4. `reason`: LLM → `{ incident_type: restricted_area_intrusion,
   severity: high, reason: "unauthorized entry to restricted area during
   after-hours (22:40)", matched_policy:
   "restricted_area_policy#entry-response", recommended_action: "Dispatch
   on-site guard; preserve snapshot; notify facility manager",
   report_summary: "At 22:40 a person entered the restricted Server Room
   Door zone …" }`.
5. `build_report` → markdown; `persist` → DB; `notify` → n8n → security
   team's Telegram/email.
