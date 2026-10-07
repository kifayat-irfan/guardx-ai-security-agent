# GuardX — AI Autonomous Security Agent

Real-time incident detection and response for physical security.

**Scenario:** a person enters a restricted area → YOLO detects the person →
the zone engine flags the intrusion → a structured security incident is created →
a LangGraph workflow retrieves the relevant security policy (RAG), an LLM reasons
over incident + policy, classifies severity, generates a report → the Next.js
dashboard shows the incident and the AI's decision → n8n optionally sends
external notifications.

## Team

| Member       | Role (suggested)              |
|--------------|-------------------------------|
| Kifayat Irfan  | Lead — AI / backend / LangGraph |
| Abdur Razzaq   | Computer Vision / zone engine   |
| Abdur Rehman   | Frontend (Next.js) / n8n        |

## Current status: Phase 0 — planning & architecture (complete)

This repository currently contains the **Phase 0 deliverables**: inspected
workspace, clean project structure, architecture, and a phased build plan.
No phase implementation code yet — that starts with Phase 1.

## Documentation (Phase 0 deliverables)

| Doc | Contents |
|-----|----------|
| `docs/01-architecture.md` | Final architecture, module definitions, tech decisions, Docker services, dependencies, risks |
| `docs/02-database-design.md` | Entities, ER diagram, table definitions |
| `docs/03-api-design.md` | REST endpoints (v1) with request/response shapes |
| `docs/04-langgraph-workflow.md` | Graph state, nodes, edges, decision schema |
| `docs/05-rag-design.md` | RAG pipeline, chunking, embedding config, policy corpus design |
| `docs/06-implementation-plan.md` | Phases 1–10 with exit criteria + tests per phase |
| `docs/07-phase1-commands.md` | Exact commands to execute Phase 1 |

## Repository layout

```
guardx/
├── backend/            # FastAPI (Python) — vision, zones, incidents, RAG, LangGraph
├── frontend/           # Next.js + TypeScript + Tailwind dashboard
├── policies/           # Security policy source documents (Phase 4)
├── n8n/workflows/      # n8n workflow exports (Phase 9)
├── assets/             # Sample videos, snapshots (not committed)
├── scripts/            # Dev/ops helper scripts
├── docs/               # Phase 0 design docs (start here)
├── .env.example        # All configuration; no hardcoded secrets
└── docker-compose.yml  # Phase 1: service orchestration (to be written)
```

## Quick start (after Phase 1)

```bash
cp .env.example .env
docker compose up --build
# backend → http://localhost:8000/docs
# frontend → http://localhost:3000
```

## Design principles

1. **RAG retrieves, it never decides.** Policy text is context; the LangGraph
   reasoning node produces the structured decision.
2. **Modular vision pipeline.** The zone engine consumes generic detection
   events, so new CV event types (loitering, object left behind, …) plug in later.
3. **Configurable AI.** LLM and embedding providers switch via env vars only.
4. **No fake completeness.** A feature is done only when its phase tests pass.
