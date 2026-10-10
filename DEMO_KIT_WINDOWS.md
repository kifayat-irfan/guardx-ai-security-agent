# GuardX — FYP Demo Kit (Windows Local Run)

**Project:** GuardX — AI Autonomous Security Agent for Real-Time Incident Detection and Response
**Team:** Kifayat Irfan (AI/backend lead) · Abdur Razzaq (computer vision / YOLO) · Abdur Rehman (frontend / n8n)
**Purpose:** Run the full GuardX system on your own Windows computer and demo it to your professor.

---

## Part 1 — Install prerequisites (one time, ~20 min)

1. **Python 3.11** — https://www.python.org/downloads/ → download 3.11.x → install karte waqt **"Add python.exe to PATH"** zaroor tick karna.
   Verify: `python --version` → `Python 3.11.x`

2. **PostgreSQL 16** — https://www.postgresql.org/download/windows/ → installer chalao.
   - Password yaad rakho (e.g. `guardx123`)
   - Port: `5432` (default)
   - Verify: Start menu → "SQL Shell (psql)" kholo, Enter dabate jao, password do.

3. **Node.js 20 LTS** — https://nodejs.org/ → LTS version install karo.
   Verify: `node --version` → `v20.x.x`

4. **Git** — https://git-scm.com/download/win → install karo.

---

## Part 2 — Project setup (one time, ~15 min)

PowerShell kholo aur:

```powershell
# 1. Repo clone karo
cd $HOME\Desktop
git clone https://github.com/kifayat-irfan/guardx-ai-security-agent.git
cd guardx-ai-security-agent

# 2. Database banao
psql -U postgres -c "CREATE USER guardx WITH PASSWORD 'guardx123';"
psql -U postgres -c "CREATE DATABASE guardx OWNER guardx;"

# 3. Backend virtual environment
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -r requirements.txt

# 4. .env file banao (backend\.env)
copy ..\.env.example .env
```

Phir `backend\.env` ko Notepad mein kholo aur ye values set karo:

```
APP_ENV=dev
DATABASE_URL=postgresql+psycopg2://guardx:guardx123@localhost:5432/guardx
FRONTEND_URL=http://localhost:3000
LLM_PROVIDER=sensenova
SENSENOVA_API_KEY=<tumhari key yahan>
SENSENOVA_BASE_URL=https://token.sensenova.ai/v1
SENSENOVA_MODEL=sensenova-6.8-flash-lite
RAG_POLICIES_DIR=../policies
```

```powershell
# 5. Database migrations
alembic upgrade head

# 6. Frontend dependencies (naya PowerShell window kholo)
cd $HOME\Desktop\guardx-ai-security-agent\frontend
npm install
```

> **Note:** `pip install` mein 5-10 minute lag sakte hain (torch, ultralytics, chromadb download honge).

---

## Part 3 — System chalao (demo se 5 min pehle)

**Terminal 1 — Backend:**
```powershell
cd $HOME\Desktop\guardx-ai-security-agent\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Browser mein kholo: http://localhost:8000/docs → "GuardX API" docs nazar aayen.

**Terminal 2 — Frontend:**
```powershell
cd $HOME\Desktop\guardx-ai-security-agent\frontend
npm run dev
```
Browser mein kholo: http://localhost:3000 → Dashboard, "backend connected" (green).

**RAG index banao (pehli baar, ~2 min):**
Browser mein kholo: http://localhost:8000/docs → `POST /api/v1/policies/reindex` → "Try it out" → "Execute".
Ya PowerShell se:
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/policies/reindex
```
Dashboard mein "Policies: 5, Indexed chunks: 20" nazar aana chahiye.

---

## Part 4 — Sir ko demo (5-7 minute ka script)

### 1. Overview (1 min)
- Dashboard kholo: http://localhost:3000
- Dikhao: "backend connected" green status, live system health
- Batao: "Ye mera Final Year Project hai — AI Autonomous Security Agent jo real-time mein security incidents detect karta hai aur khud faisla karta hai."

### 2. Architecture (1 min) — ye pipeline zubani samjhao
> Camera → **YOLO** person detection → **restricted-zone engine** → zone events → **LangGraph** workflow → **RAG** policy retrieval → **LLM** reasoning → severity/decision → **PostgreSQL** incident → live **dashboard** → optional **n8n** notification.

### 3. Live detection (2 min) — sab se impressive hissa
- Dashboard mein camera/video add karo (test video: `assets/test_videos/person_pan_test.mp4`)
- Dikhao: **real YOLO bounding boxes** with track-ID aur confidence labels
- Cinematic **HUD overlay**: REC indicator, telemetry strip, scanlines
- Jab person restricted zone mein enter kare → flashing **INTRUSION** banner

### 4. Incident + AI analysis (2 min)
- Generated incident kholo: severity, decision, audit trail
- Dikhao: **real SenseNova LLM** ne policy-grounded analysis di (citations ke saath, e.g. `restricted-area#rules`)
- Batao: "RAG sirf retrieve karta hai, faisla LangGraph workflow karta hai — ye design rule hai."

### 5. Backup: recorded demo (agar live mein kuch atke)
- `demo/GuardX-Final-Demo-V3.mp4` chalao (155 second, full pipeline: detection → RAG → SenseNova → incident)

---

## Part 5 — Sir ke likely sawalat (tayyari)

| Sawal | Jawab |
|---|---|
| YOLO kaunsa model? Kyun? | YOLOv8n (nano) pretrained. MVP mein reliability over novelty — custom training ki zaroorat nahi thi. |
| LLM kaunsa? | SenseNova `sensenova-6.8-flash-lite` (international endpoint). Real API integration, mock nahi. |
| RAG mein kya hai? | 5 security policies, 20 chunks, ChromaDB + sentence-transformers embeddings. Citations deterministic `chunk_id` se. |
| Database? | PostgreSQL, Alembic migrations (3 revisions), incidents persist hote hain. |
| n8n kis liye? | Optional notifications (Email/Telegram). By design kabhi startup block nahi karta. |
| Team mein kaam kaise divide tha? | Kifayat: AI/backend · Abdur Razzaq: computer vision · Abdur Rehman: frontend/n8n |
| Testing? | Backend 215 tests pass, frontend 17/17, TypeScript clean, production build green. |
| Live deployment? | https://guardx-dashboard.vercel.app (frontend) + Render backend — free tier par RAG memory limit hai, is liye local demo full pipeline dikhata hai. |

---

## Part 6 — Troubleshooting (Windows)

| Masla | Hal |
|---|---|
| `pip install` fail | Python 3.11 confirm karo (`python --version`). 3.12+ par kuch packages issue de sakte hain. |
| PostgreSQL connect nahi ho raha | Service chal rahi hai? Start menu → Services → `postgresql-x64-16` → Running honi chahiye. |
| Port 8000 busy | `netstat -ano \| findstr :8000` → PID dekho → Task Manager se kill karo. |
| Frontend "Backend unavailable" | Pehle backend chalao (Terminal 1), phir frontend refresh karo. |
| YOLO slow hai | Normal hai CPU par — `FRAME_SKIP=2` pehle se set hai. Demo video choti hai, chal jayegi. |

---

## Quick links

- **Live dashboard:** https://guardx-dashboard.vercel.app
- **Live backend:** https://guardx-api-amuo.onrender.com
- **API docs:** https://guardx-api-amuo.onrender.com/docs
- **GitHub:** https://github.com/kifayat-irfan/guardx-ai-security-agent
- **Demo video:** repo mein `demo/GuardX-Final-Demo-V3.mp4`

---

*Good luck! Tum ne ye system khud banaya hai — confident raho. Sir ko pipeline samjhao, live detection dikhao, aur honest raho jahan limitation ho (free-tier RAG). Examiners honesty ko respect karte hain.*
