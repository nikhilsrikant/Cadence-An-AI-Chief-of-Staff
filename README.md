# Cadence: An AI Chief of Staff

> **Most AI tools answer questions. Cadence closes the loop — from what got decided in a meeting to what actually gets done.**

Built on **IBM watsonx Orchestrate** for the IBM watsonx Orchestrate Hackathon.

---

## The Problem

Knowledge workers lose hours a week to a specific kind of friction: a decision gets made in a meeting, and then it evaporates. Someone has to remember it, chase the owner, catch the deadline slipping, and notice when two commitments collide on the same person's calendar.

**Existing AI copilots summarize the meeting — they don't own what happens next.**

---

## What Cadence Does

Cadence sits across a team's communication surfaces and turns **"what was said"** into **"what gets closed out"**:

| Capability | Description |
|-----------|-------------|
| **Commitment Extraction** | Ingests Slack threads, calendar invites, and meeting transcripts. Pulls out structured commitments: decision, owner, deadline, dependency. |
| **Cross-Tool Knowledge Graph** | Live Neo4j graph linking people, decisions, and tasks. Detects conflicts invisible to single tools. |
| **Autonomous Orchestration Agents** | Scheduler, follow-up, and escalation agents that act on the graph: nudging owners, proposing reschedules, escalating stalled items. |
| **Decision Dashboard** | Daily "what needs a decision from you" view, ranked by urgency, impact, and blocking count. |
| **Human Approval Gate** | Every autonomous action passes through an approval checkpoint with configurable auto-clear. Trust is the product, not a feature. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                    │
│   Slack Threads  •  Calendar Invites  •  Meeting Transcripts            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              EXTRACTION AGENT (watsonx Orchestrate + Granite)           │
│   Turns unstructured text → structured commitments & decisions          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH (Neo4j)                              │
│   Nodes: Person, Commitment, Decision, Meeting, Conflict, AgentAction   │
│   Edges: OWNS, DEPENDS_ON, BLOCKS, MADE_DECISION, TARGETS               │
└───────────────────┬─────────────────────────────┬───────────────────────┘
                    │                             │
                    ▼                             ▼
┌──────────────────────────────┐  ┌──────────────────────────────────────┐
│     DECISION DASHBOARD       │  │       ORCHESTRATION AGENTS           │
│  Daily prioritized view      │  │                                      │
│  Ranked by:                  │  │  ┌────────────┐  ┌──────────────┐    │
│  • Urgency                   │  │  │ Scheduler  │  │  Follow-up   │    │
│  • Impact                    │  │  │(determin.) │  │ (generative) │    │
│  • Blocking count            │  │  └────────────┘  └──────────────┘    │
│                              │  │        ┌──────────────┐              │
│                              │  │        │  Escalation  │              │
│                              │  │        │(determin.)   │              │
│                              │  │        └──────────────┘              │
└──────────────────────────────┘  └──────────────────┬───────────────────┘
                                                     │
                                                     ▼
                                  ┌──────────────────────────────────────┐
                                  │        HUMAN APPROVAL GATE           │
                                  │  • Auto-clear if confidence ≥ 0.7    │
                                  │  • Manual review otherwise           │
                                  │  • Full audit trail                  │
                                  └──────────────────┬───────────────────┘
                                                     │
                                                     ▼
                                  ┌──────────────────────────────────────┐
                                  │        AUTONOMOUS ACTIONS            │
                                  │  Nudges • Reschedules • Task Sync    │
                                  └──────────────────────────────────────┘
```

---

## How We Built It

We built the orchestration layer on **watsonx Orchestrate** rather than a bespoke agent framework:

| Layer | watsonx Orchestrate Feature |
|-------|---------------------------|
| **Ingestion** | Connector catalog (150+ enterprise connectors: Microsoft 365, Salesforce, ServiceNow) |
| **Extraction** | Orchestrate skill backed by **Granite** foundation model on watsonx.ai |
| **Knowledge Graph** | External Neo4j service wired as a custom tool |
| **Orchestration** | Flow builder with multiple decision styles: deterministic + generative |
| **Governance** | Agentic Control Plane + Security Control Center |

### Agent Decision Styles

| Agent | Style | Why |
|-------|-------|-----|
| **Scheduler** | Deterministic | Predictable conflict detection and rule-based reschedule proposals |
| **Follow-up** | Generative | Natural-language nudges that vary for a human feel |
| **Escalation** | Deterministic | Clear rules for when and how to escalate — auditable and predictable |

---

## Tech Stack

| Technology | Role |
|-----------|------|
| [watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) | Multi-agent orchestration platform |
| [watsonx.ai (Granite)](https://www.ibm.com/granite) | Foundation model for commitment extraction |
| [Neo4j](https://neo4j.com/) | Knowledge graph database |
| [FastAPI](https://fastapi.tiangolo.com/) | Backend REST API |
| [Streamlit](https://streamlit.io/) | Decision dashboard frontend |
| [Docker Compose](https://docs.docker.com/compose/) | Container orchestration |

---

## Project Structure

```
Cadence-An-AI-Chief-of-Staff/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/
│   │   └── routes.py            # All REST endpoints
│   ├── agents/
│   │   ├── base_agent.py        # Abstract base agent
│   │   ├── scheduler_agent.py   # Conflict detection + reschedules
│   │   ├── followup_agent.py    # Nudge generation
│   │   ├── escalation_agent.py  # Escalation logic
│   │   ├── orchestrator.py      # Runs all agents in sequence
│   │   └── approval_gate.py     # Human approval gate
│   ├── extraction/
│   │   ├── extractor.py         # Commitment extraction engine
│   │   └── prompts.py           # Granite model prompts
│   ├── graph/
│   │   ├── database.py          # Neo4j driver + operations
│   │   └── schema.py            # Graph constraints + indexes
│   ├── models/
│   │   └── schemas.py           # Pydantic domain models
│   └── utils/
│       └── logger.py            # Logging configuration
├── frontend/
│   └── app.py                   # Streamlit dashboard (7 pages)
├── config/
│   └── settings.py              # Centralized configuration
├── demo/
│   ├── sample_transcript.txt    # Sample meeting transcript
│   ├── seed_data.py             # Pre-load graph for demo
│   └── demo_runner.py           # Scripted 4-step demo
├── docker-compose.yml           # Full stack deployment
├── Dockerfile                   # Backend container
├── Dockerfile.dashboard         # Dashboard container
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
└── README.md                    # This file
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- IBM watsonx.ai API key (for LLM extraction; fallback available without it)

### 1. Clone & Configure

```bash
git clone https://github.com/nikhilsrikant/Cadence-An-AI-Chief-of-Staff.git
cd Cadence-An-AI-Chief-of-Staff

# Copy and edit environment variables
cp .env.example .env
# Add your WATSONX_API_KEY and WATSONX_PROJECT_ID (optional for demo)
```

### 2. Launch with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **Neo4j** — `http://localhost:7474` (browser) / `bolt://localhost:7687`
- **Backend API** — `http://localhost:8000` (docs at `/docs`)
- **Dashboard** — `http://localhost:8501`

### 3. Seed Demo Data

```bash
# In a separate terminal
docker exec cadence-backend python -m demo.seed_data
```

### 4. Open the Dashboard

Navigate to **http://localhost:8501** to see the full decision dashboard.

---

## Demo Flow for Judges

The demo follows 4 steps that showcase Cadence's core loop:

### Step 1: Ingest Meeting Transcript
Upload the sample Q4 Planning Meeting transcript → watch commitments populate the knowledge graph in real-time.

### Step 2: Trigger Conflict Detection
Two commitments for Lisa Wong land on the same day (SOC2 review + auth module review) → Cadence's scheduler agent detects the conflict and proposes a reschedule.

### Step 3: Human Approval Gate
The proposed reschedule appears in the approval queue → one-click approve → nudge goes out, calendar update proposed.

### Step 4: Decision Dashboard
View the prioritized dashboard showing all open items ranked by urgency, impact, and how many downstream items each is blocking.

### Run the Demo Programmatically

```bash
docker exec cadence-backend python -m demo.demo_runner
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `POST` | `/api/ingest` | Ingest transcript → extract commitments |
| `GET` | `/api/commitments` | List all commitments |
| `GET` | `/api/decisions` | List all decisions |
| `GET` | `/api/conflicts` | Detect schedule/overload/blocking conflicts |
| `GET` | `/api/dashboard` | Prioritized decision dashboard |
| `GET` | `/api/approvals` | Pending agent actions |
| `POST` | `/api/approvals/review` | Approve or reject action |
| `POST` | `/api/agents/run` | Trigger all agents |
| `GET` | `/api/graph/export` | Export full graph for visualization |

Full OpenAPI docs available at `http://localhost:8000/docs`.

---

## Why This Fits the Brief

| Criterion | How Cadence Delivers |
|-----------|---------------------|
| **Reduce repetitive work** | Follow-up and status-chasing becomes an autonomous, approved nudge |
| **Improve decision-making** | Graph surfaces conflicts and blocking chains invisible to any single tool |
| **Help teams reach outcomes faster** | Closes the loop from "decided in meeting" to "reflected in task tracker" |

---

## What's Next

Post-hackathon, the natural extension is publishing Cadence's agents to **Orchestrate's reusable agent catalogue** so other teams can adopt the scheduler/follow-up/escalation trio without rebuilding them — the direction IBM's platform is already pushing enterprise customers toward.

---

## Team
Nikhil Srikant Kulkarni
Aishwarya Hareesh Rao
Built for the IBM watsonx Orchestrate Hackathon.

---

## License

MIT
