<h1 align="center">TrueNorth-AI</h1>

<p align="center">
  <strong>AI-powered patient access assistant for hospitals running OpenMRS/Bahmni</strong><br />
  Book doctors, understand lab results, track your queue — all through WhatsApp or web chat.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/next.js-14+-black?logo=next.js" />
  <img src="https://img.shields.io/badge/LangGraph-agent-green" />
  <img src="https://img.shields.io/badge/Claude-Sonnet%20%7C%20Opus-orange?logo=anthropic" />
  <img src="https://img.shields.io/badge/OpenMRS-integrated-red" />
</p>
<p>To access the application click on the link below</p>
<a href="http://3.92.134.232:3000/login">TrueNorth-AI</a>

<br>

<!-- TODO: Add hero screenshot or demo GIF -->

![Login Screen](frontend/public/loginscreen.png)

<br>

![Main Chat](frontend/public/mainChat.png)

---

## What It Does

Patients interact with a single AI assistant — via WhatsApp or a web app — that connects directly to the hospital's OpenMRS/Bahmni system. No apps to install, no portals to learn.

<!-- TODO: Add side-by-side screenshot: WhatsApp conversation on the left, web app on the right -->
<!-- <p align="center">
  <img src="docs/assets/dual-channel.png" alt="WhatsApp and Web side by side" width="750" />
</p> -->

**Find & book a doctor** — _"I need a dermatologist this week"_ → agent checks real availability, presents slots, books the appointment, and sends reminders as the date approaches.

**Understand your results** — When a doctor files a lab result or prescription, the patient gets an automatic plain-language explanation via WhatsApp within seconds. Patients can also upload external reports (photos or PDFs) for interpretation.

**Know your queue position** — Real-time queue tracking with estimated wait time. Get notified when you're next instead of sitting in the lobby guessing.

**Smart reminders** — Context-aware follow-up notifications that suggest optimal rebooking times based on hospital busyness. Confirm, cancel, or reschedule directly from the reminder.

**Symptom triage** — Describe symptoms conversationally. The agent asks structured questions, assesses urgency using the ESI framework, and routes to the right specialist — with a one-tap transition into booking.

---

## How It Works

<!-- TODO: Add architecture diagram (Excalidraw or Figma export) -->
<!-- <p align="center">
  <img src="docs/assets/architecture.png" alt="System Architecture" width="750" />
</p> -->

MediAgent is built on a **hybrid MCP + LangGraph architecture**:

An **OpenMRS MCP Server** wraps the hospital's REST API behind standardized tool definitions — `search_services`, `create_appointment`, `get_lab_results`, `get_queue_status`, and others. This means if the EMR changes, only the MCP server internals change; nothing else in the system is affected.

A **LangGraph agent orchestrator** controls the multi-step workflows. When a patient says "book me a dermatologist," LangGraph — not the LLM — decides which MCP tools to call, in what order, and how to handle errors. The LLM's job is understanding language and composing responses; LangGraph manages the state machine.

Both channels (WhatsApp and web) feed into the **same agent logic** through a FastAPI gateway. The only difference is response formatting — WhatsApp gets plain text, the web app gets structured JSON that renders as interactive React components.

New lab results and prescriptions trigger **instant notifications** via OpenMRS Event Module → ActiveMQ → MediAgent. No polling — the patient gets their explanation seconds after the doctor files it.

**LLM routing** is split by task type within a single provider (Anthropic): Claude Sonnet handles fast tasks (intent classification, slot filling, status checks) while Claude Opus handles complex reasoning (medical report interpretation, symptom triage).

---

## Tech Stack

|                     | Technology                                   |
| ------------------- | -------------------------------------------- |
| **Frontend**        | Next.js 14+, shadcn/ui, Tailwind CSS         |
| **Backend**         | FastAPI (Python, async)                      |
| **AI Agent**        | LangGraph, Claude Sonnet + Opus (Anthropic)  |
| **EMR Integration** | OpenMRS MCP Server (SSE transport)           |
| **Events**          | OpenMRS Event Module + ActiveMQ              |
| **Database**        | PostgreSQL                                   |
| **Messaging**       | WhatsApp Business API (Meta Cloud)           |
| **Real-time**       | Server-Sent Events (SSE)                     |
| **Monitoring**      | LangSmith (AI traces) + Prometheus + Grafana |
| **Deployment**      | Docker Compose (dev), AWS ECS Fargate (prod) |

---

## Getting Started

### Prerequisites

Docker & Docker Compose, Node.js 18+, Python 3.11+, an Anthropic API key, and Meta Cloud API credentials for WhatsApp.

### Run Locally

```bash
git clone https://github.com/yourusername/mediagent.git
cd mediagent
cp .env.example .env   # Add your API keys
docker-compose up -d
```

| Service        | URL                           |
| -------------- | ----------------------------- |
| Web App        | http://localhost:3000         |
| FastAPI Docs   | http://localhost:8000/docs    |
| OpenMRS/Bahmni | http://localhost:8080/openmrs |
| Grafana        | http://localhost:3001         |

### Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENMRS_BASE_URL=http://openmrs:8080/openmrs
OPENMRS_USERNAME=admin
OPENMRS_PASSWORD=Admin123
MCP_SERVER_URL=http://mcp-server:8001/sse
DATABASE_URL=postgresql+asyncpg://mediagent:password@postgres:5432/mediagent
ACTIVEMQ_BROKER_URL=tcp://activemq:61616
META_PHONE_NUMBER_ID=...
META_ACCESS_TOKEN=...
META_APP_SECRET=...
JWT_SECRET_KEY=...
```

Full variable reference in [`.env.example`](.env.example).

---

## Roadmap

- [x] Architecture design & PRD
- [ ] LangGraph agent with intent classification and subgraph routing
- [ ] OpenMRS MCP Server
- [ ] Appointment booking (WhatsApp + Web)
- [ ] Symptom triage
- [ ] Report & prescription interpretation
- [ ] Proactive reminders
- [ ] Live queue tracking
- [ ] Multi-language support (Kinyarwanda, French, Swahili)
- [ ] Doctor-side dashboard
- [ ] AWS production deployment

---

## Documentation

Detailed technical documentation lives in Mediagent file:

- [MediAgent-Technical-PRD](MediAgent-Technical-PRD.md) — Full system design, data models, agent topology, auth flows, API mappings
- [OpenMRS Documentation](https://rest.openmrs.org/?java#openmrs-rest-api) — Knowledge base integration reference

---

<p align="center">
  Built by <strong>Alain Mugisha</strong>
</p>
