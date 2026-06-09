<p align="center">
  <!-- TODO: Replace with actual logo -->
  <img src="/home/alain/Alain/TrueNorth-AI/frontend/app/shield.png" alt="TrueNorth-AI Logo" width="100" />
</p>

<h1 align="center">TrueNorth-AI</h1>

<p align="center">
  <strong>AI-Powered Patient Access Assistant for Hospitals and Clinics</strong>
</p>

<p align="center">
  An agentic AI system that connects patients to their hospital through natural conversation — enabling doctor discovery, appointment booking, medical report interpretation, proactive reminders, live queue tracking, and symptom triage — delivered via WhatsApp and a modern web interface.
</p>

<p align="center">
  <a href="#architecture">Architecture</a> •
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#project-structure">Project Structure</a> •
  <a href="#how-it-works">How It Works</a>
</p>

<br />

<!-- TODO: Add hero screenshot or demo GIF -->
 <p align="center">
  <img src="/home/alain/Alain/TrueNorth-AI/frontend/public/loginscreen.png" alt="TrueNorth-AI Demo" width="800" />
</p> 
<br>
 <p align="center">
  <img src="/home/alain/Alain/TrueNorth-AI/frontend/public/mainChat.png" alt="TrueNorth-AI Demo" width="800" />
</p>

---

## The Problem

Patients visiting hospitals running OpenMRS/Bahmni face a fragmented, time-consuming experience. Checking doctor availability requires phone calls or physical visits. Medical reports arrive as raw numbers without explanation. Follow-up appointments slip through the cracks. And the waiting room queue? You sit for hours with no visibility into when your turn arrives.

TrueNorth-AI eliminates this friction. A patient sends a WhatsApp message like _"I need to see a dermatologist this week"_ and the AI agent checks real doctor availability in OpenMRS, presents available slots, books the appointment, and sends reminders as the date approaches — all through conversation.

---

## Architecture

TrueNorth-AI is built on a **hybrid MCP + LangGraph architecture** — a pattern where an MCP server standardizes the tool interface over OpenMRS REST APIs, while LangGraph controls the stateful multi-step workflows that determine when and how those tools are called. Neither pattern alone is sufficient: MCP without LangGraph means trusting the LLM to manage multi-step booking flows reliably (it won't). LangGraph without MCP means baking API integrations directly into agent code (not portable).

<!-- TODO: Add architecture diagram -->
<!-- <p align="center">
  <img src="docs/assets/architecture-diagram.png" alt="System Architecture" width="800" />
</p> -->

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PATIENT CHANNELS                            │
│  ┌─────────────────────────┐   ┌──────────────────────────────────┐│
│  │   WhatsApp (Meta Cloud) │   │   Next.js Web App               ││
│  │   Chat-only interface   │   │   Chat-first + side panels      ││
│  └───────────┬─────────────┘   └────────────┬─────────────────────┘│
└──────────────┼──────────────────────────────┼──────────────────────┘
               │ Webhook POST                 │ BFF (API routes)
               ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Unified API Gateway)                 │
│  • Channel normalization  • Session management  • SSE streaming    │
│  • APScheduler (reminders)  • ActiveMQ consumer (EMR events)       │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│               LangGraph Agent Orchestrator                         │
│  Intent Classification → Subgraph Routing → Channel Formatting     │
│  ├── BookingSubgraph       ├── TriageSubgraph                      │
│  ├── ReportSubgraph        ├── QueueSubgraph                       │
│  └── ReminderSubgraph                                              │
│                                                                    │
│  LLM Routing: Sonnet (fast tasks) | Opus (complex reasoning)      │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ MCP Client (SSE)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│               OpenMRS MCP Server (separate container)              │
│  Standardized tool definitions over OpenMRS REST API               │
│  search_services • create_appointment • get_lab_results • ...      │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                    ┌──────┴───────┐
                    ▼              ▼
          ┌──────────────┐  ┌──────────────┐
          │ OpenMRS/Bahmni│  │  PostgreSQL  │
          │ REST API      │  │              │
          │ ActiveMQ      │  │              │
          └──────────────┘  └──────────────┘
```

**Key architectural decisions and why:**

- **Dual-channel, single brain.** Both WhatsApp and the web app feed into the same LangGraph agent through a unified API gateway. The agent logic is identical — only the response formatting differs. WhatsApp gets plain text with numbered lists; the web app gets structured JSON that renders as React components (appointment cards, lab result modals, queue badges).

- **Event-driven, not polling.** New lab results and prescriptions trigger instant patient notifications via OpenMRS Event Module → ActiveMQ → TrueNorth-AI consumer. No 5-minute polling delay — the patient gets their report explanation within seconds of the doctor filing it.

- **Intelligent model routing within a single provider.** All LLM calls stay within Anthropic. Claude Sonnet handles fast, low-reasoning tasks (intent classification, slot filling, status formatting). Claude Opus handles complex reasoning (medical report interpretation, symptom triage). The routing is hardcoded by task type, not dynamic — predictable cost and latency.

- **State machine, not pipeline.** LangGraph's graph-based architecture means a failing node doesn't crash the entire flow. Errors write to shared state, conditional edges route to retry/fallback/graceful-failure paths. The patient always gets a response, even when OpenMRS is temporarily unreachable.

---

## Features

### 1. Doctor Discovery & Appointment Booking

Patient describes what they need in natural language. The agent resolves the specialty, queries available services and their capacity from OpenMRS, generates candidate time slots, and books upon confirmation — all via MCP tools orchestrated by LangGraph.

<!-- TODO: Add booking flow screenshot/GIF -->
<!-- <p align="center">
  <img src="docs/assets/feature-booking.png" alt="Booking Flow" width="700" />
</p> -->

**Technical highlights:**

- Bahmni Appointments uses a service-capacity model (no discrete slots). A LangGraph node generates candidate times from service hours + `durationMins`, gated by daily capacity via `get_service_load` and conflict checking via `check_appointment_conflicts`
- Appointment written to OpenMRS via MCP `create_appointment` tool and mirrored to PostgreSQL `appointment_records`
- Reminder entries auto-generated at 7 days, 1 day, and 2 hours before the appointment

### 2. Medical Report & Prescription Interpretation

When a doctor files a lab result or prescription in OpenMRS, the Event Module fires an ActiveMQ event. TrueNorth-AI's consumer picks it up, deduplicates against the delivery log, fetches the full data via MCP tools, and triggers Claude Opus to generate a plain-language explanation.

For prescriptions, the doctor's own instructions and warnings from the `dosingInstructions` field in OpenMRS are the primary source — the LLM enriches with its medical knowledge, not the other way around.

<!-- TODO: Add report interpretation screenshot -->
<!-- <p align="center">
  <img src="docs/assets/feature-reports.png" alt="Report Interpretation" width="700" />
</p> -->

**Technical highlights:**

- Event-driven via ActiveMQ (not polling) — sub-second detection of new results
- WhatsApp 24-hour window management: free-form message within window, pre-approved template message outside it
- Patients can also upload external reports (images/PDFs) via WhatsApp or web — Claude Vision handles image-based documents, `pypdf` handles PDFs
- Every explanation includes a mandatory medical disclaimer and low-confidence fallback ("please discuss with your doctor")

### 3. Symptom Pre-Screening & Triage Routing

A multi-turn conversational triage using the ESI (Emergency Severity Index) 5-level framework. The agent asks structured clarifying questions about onset, severity, trajectory, and red-flag symptoms, then recommends the appropriate department and urgency level. Emergency red flags trigger immediate ESI-1 classification and bypass the normal question flow.

<!-- TODO: Add triage flow screenshot -->
<!-- <p align="center">
  <img src="docs/assets/feature-triage.png" alt="Triage Flow" width="700" />
</p> -->

**Technical highlights:**

- Claude Opus with a comprehensive clinical triage system prompt (see Section 23 of the Technical PRD)
- Emits structured triage JSON alongside the patient-facing message for audit and clinical review
- Medical history context from previous report interpretations is injected when available — treated as unverified background, never overriding patient self-report
- Seamless handoff to the booking flow when the patient accepts the recommendation

### 4. Proactive Follow-Up & Smart Reminders

APScheduler scans `reminder_schedules` every 60 seconds. Due reminders are personalized with doctor name, appointment type, and hospital busyness context. Patients can confirm, cancel, or reschedule directly from the reminder message.

**Technical highlights:**

- Reminder entries are generated automatically when appointments are booked or when `MedicationRequest` events arrive from OpenMRS
- Hospital busyness data from `get_hospital_busyness_patterns` MCP tool informs rebooking suggestions
- WhatsApp template messages (pre-approved by Meta) for reminders outside the 24-hour conversation window
- Delivery status tracking: pending → sent → delivered → read / failed

### 5. Live Queue Tracking

Integrates with the OpenMRS Queue Module REST API. Web app shows a live queue badge in the side panel; WhatsApp provides on-demand text status. Booked patients arriving 10+ minutes early get priority placement.

**Technical highlights:**

- Queue position and ETA from OpenMRS via MCP `get_queue_status` tool
- Proactive WhatsApp notification when patient is within 2 positions of being called
- Edge case handling: doctor breaks (queue pauses), appointment overruns (ETA recalculates), patient leaves queue (cleanup)

---

## Tech Stack

| Layer            | Technology                         | Why                                                              |
| ---------------- | ---------------------------------- | ---------------------------------------------------------------- |
| Web Frontend     | Next.js 14+ (App Router)           | SSR, React Server Components, BFF pattern                        |
| UI               | shadcn/ui + Tailwind CSS           | Composable components, no dependency lock-in                     |
| Web Auth         | NextAuth.js (email OTP)            | JWT access + refresh tokens with rotation and reuse detection    |
| Backend API      | FastAPI (Python, async)            | High-performance async, native Pydantic validation               |
| AI Orchestration | LangGraph                          | Stateful graph-based agent workflows with checkpoint persistence |
| LLM (Fast)       | Claude Sonnet 4                    | Intent classification, slot filling, formatting                  |
| LLM (Complex)    | Claude Opus 4                      | Medical reasoning, report interpretation, triage                 |
| EMR Integration  | OpenMRS MCP Server (SSE)           | Standardized tool interface over OpenMRS REST API                |
| Event Streaming  | OpenMRS Event Module + ActiveMQ    | Push events for new patients, labs, prescriptions                |
| Database         | PostgreSQL                         | Patient mappings, sessions, reminders, delivery logs             |
| Messaging        | WhatsApp Business API (Meta Cloud) | Direct Meta integration, template message support                |
| Background Jobs  | APScheduler                        | Reminder scanning every 60 seconds                               |
| Real-time (Web)  | Server-Sent Events (SSE)           | LLM token streaming, queue updates                               |
| Monitoring       | LangSmith + Prometheus + Grafana   | AI traces + infrastructure metrics                               |
| Dev Deployment   | Docker Compose                     | Full local stack including OpenMRS                               |

---

## Project Structure

```
TrueNorth-AI/
├── backend/                          # FastAPI application
│   ├── main.py                       # App factory, lifespan, router registration
│   ├── core/
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── database.py               # SQLAlchemy async engine + session
│   │   └── security.py               # OTP generation, JWT creation/verification
│   ├── agent/
│   │   ├── graph.py                  # Parent LangGraph graph definition
│   │   ├── state.py                  # AgentState schema (Pydantic)
│   │   ├── nodes/                    # Node implementations (classify, format, deliver)
│   │   ├── subgraphs/               # Feature subgraphs (booking, triage, reports, queue, reminders)
│   │   └── mcp_client.py            # MCP client setup (SSE connection)
│   ├── features/                     # Feature-based modules
│   │   ├── booking/                  # Router, service, schemas
│   │   ├── triage/
│   │   ├── reports/
│   │   ├── queue/
│   │   └── reminders/
│   ├── events/
│   │   ├── activemq_consumer.py     # ActiveMQ subscriber (lifespan task)
│   │   └── handlers.py              # Event dispatch (patient created, lab filed, etc.)
│   ├── whatsapp/
│   │   ├── router.py                # Webhook endpoint + signature verification
│   │   ├── client.py                # Meta Cloud API client
│   │   └── templates.py             # Template message definitions
│   ├── scheduler/
│   │   └── reminder_scanner.py      # APScheduler job definitions
│   └── models/
│       └── db.py                    # SQLAlchemy ORM models
│
├── mcp_server/                       # OpenMRS MCP Server (separate container)
│   ├── server.py                    # MCP server entry point, tool registration
│   ├── openmrs_client.py            # Async HTTP client for OpenMRS REST API
│   └── tools/
│       ├── patient.py               # get_patient_by_identifier
│       ├── appointments.py          # list_specialities, search_services, create_appointment, etc.
│       ├── lab_results.py           # get_patient_lab_results
│       ├── prescriptions.py         # get_patient_prescriptions
│       ├── queue.py                 # get_queue_status
│       └── analytics.py            # get_hospital_busyness_patterns
│
├── frontend/                         # Next.js 14+ web application
│   ├── app/
│   │   ├── layout.tsx               # Root layout, SessionProvider
│   │   ├── login/page.tsx           # Phone + email → OTP verification
│   │   ├── chat/
│   │   │   ├── page.tsx             # Main chat interface
│   │   │   ├── components/          # ChatPanel, MessageBubble, MessageInput, Modals
│   │   │   └── panels/             # Side panels (Appointments, Reports, Queue, History)
│   │   └── api/                    # BFF routes (auth, chat proxy, data fetching)
│   ├── lib/
│   │   ├── auth.ts                 # NextAuth config
│   │   ├── api-client.ts           # Typed FastAPI client
│   │   └── sse.ts                  # SSE streaming hook
│   ├── components/ui/              # shadcn/ui components
│   └── middleware.ts               # Route protection
│
├── docker-compose.yml                # Full local development stack
├── docs/
│   ├── assets/                      # Architecture diagrams, screenshots
│   └── prd/                        # Product requirements documents
└── README.md
```

---

## How It Works

### Booking an Appointment (End-to-End)

<!-- TODO: Add sequence diagram or flow illustration -->
<!-- <p align="center">
  <img src="docs/assets/flow-booking.png" alt="Booking Flow Diagram" width="800" />
</p> -->

```
Patient (WhatsApp): "I need to see a skin doctor this week"
         │
         ▼
    Meta Cloud API webhook → FastAPI
         │
         ▼
    Normalize message + attach patient context
         │
         ▼
    LangGraph: classify_intent (Claude Sonnet)
    → intent: "booking", specialty: "dermatology"
         │
         ▼
    BookingSubgraph:
    ├─ list_specialities (MCP) → resolve "dermatology" UUID
    ├─ search_services (MCP) → fetch dermatology services + hours + capacity
    ├─ generate_candidate_slots (LangGraph node) → compute available times
    ├─ get_service_load (MCP) → gate by daily capacity
    ├─ Present options to patient:
    │   "Dr. Uwimana — Dermatology
    │    1. Wed 18 Jun at 09:00
    │    2. Wed 18 Jun at 10:30
    │    3. Thu 19 Jun at 14:00
    │    Reply with a number to book."
    │
    ├─ Patient replies: "1"
    ├─ check_appointment_conflicts (MCP) → verify no conflicts
    ├─ create_appointment (MCP) → write to OpenMRS
    ├─ Mirror to PostgreSQL appointment_records
    ├─ Generate reminder_schedules (7d, 1d, 2h)
    └─ Confirmation:
        "Booked ✓ Dr. Uwimana | Dermatology | Wed 18 Jun at 09:00
         I'll remind you before the appointment."
```

### New Lab Result (Event-Driven)

```
Doctor files CBC result in OpenMRS/Bahmni
         │
         ▼
    OpenMRS Event Module → ActiveMQ: OBS.CREATED
         │
         ▼
    TrueNorth-AI ActiveMQ consumer receives event
         │
         ▼
    Check report_delivery_log → not yet delivered → continue
         │
         ▼
    ReportInterpretationSubgraph (LangGraph):
    ├─ get_patient_lab_results (MCP) → fetch structured result data
    ├─ Claude Opus generates plain-language explanation:
    │   "Your hemoglobin is 9.2 g/dL. The typical range is
    │    12.0–17.5 g/dL, so yours is below normal. This could
    │    mean your red blood cell count is lower than expected.
    │    Please discuss this with your doctor at your next visit.
    │
    │    ⚕️ This is informational only, not medical advice."
    │
    ├─ Check WhatsApp 24h window:
    │   ├─ Active → send free-form message
    │   └─ Expired → send template: "New results are ready..."
    └─ Log delivery in report_delivery_log
```

### Mid-Conversation Interrupt & Resume

```
Patient: "I need to book a dermatologist"
Agent: "I found Dr. Uwimana available on..."
Patient: "Wait — what's my queue number right now?"
         │
         ▼
    classify_intent detects intent ≠ current_flow
    → Save booking state to pending_intent
    → Route to QueueSubgraph
         │
         ▼
Agent: "You're #4 in line. Estimated wait: 15 minutes."
Agent: "Would you like to continue booking your dermatology appointment?"
Patient: "Yes"
         │
         ▼
    Restore pending_intent → resume BookingSubgraph
```

---

## Authentication & Patient Identity

TrueNorth-AI uses a **single identity model** — one OpenMRS Patient ID anchors both the WhatsApp and web channels.

**Patient auto-sync:** When hospital staff register a patient in OpenMRS, an ActiveMQ event fires. TrueNorth-AI automatically creates a local patient record with the synced phone and email — no separate registration step needed.

**WhatsApp linking:** First-time WhatsApp users verify their identity with their hospital Patient ID + OTP, linking their phone number to their OpenMRS record.

**Web authentication:** NextAuth.js with email-based OTP. Access + refresh JWT tokens with rotation and reuse detection. The BFF holds tokens server-side (httpOnly cookies) — the browser never sees raw JWTs.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- An OpenMRS/Bahmni instance (or use the Docker Compose dev setup)
- Meta Cloud API credentials (for WhatsApp)
- Anthropic API key

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/TrueNorth-AI.git
cd TrueNorth-AI

# Copy environment template
cp .env.example .env
# Edit .env with your API keys and configuration

# Start the full stack
docker-compose up -d

# The following services will be available:
# - Next.js frontend:     http://localhost:3000
# - FastAPI backend:      http://localhost:8000
# - FastAPI docs:         http://localhost:8000/docs
# - OpenMRS MCP Server:   http://localhost:8001/sse
# - OpenMRS/Bahmni:       http://localhost:8080/openmrs
# - Grafana dashboards:   http://localhost:3001
# - Prometheus:           http://localhost:9090
```

### Environment Variables

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenMRS
OPENMRS_BASE_URL=http://openmrs:8080/openmrs
OPENMRS_USERNAME=admin
OPENMRS_PASSWORD=Admin123

# MCP Server
MCP_SERVER_URL=http://mcp-server:8001/sse

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://TrueNorth-AI:password@postgres:5432/TrueNorth-AI

# ActiveMQ
ACTIVEMQ_BROKER_URL=tcp://activemq:61616

# WhatsApp (Meta Cloud API)
META_PHONE_NUMBER_ID=...
META_ACCESS_TOKEN=...
META_APP_SECRET=...
META_VERIFY_TOKEN=...

# Auth
JWT_SECRET_KEY=...
OTP_EXPIRY_SECONDS=300

# LangSmith (optional, for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=TrueNorth-AI-dev
```

---

## Data Model

<!-- TODO: Add ERD diagram -->
<!-- <p align="center">
  <img src="docs/assets/erd.png" alt="Entity Relationship Diagram" width="800" />
</p> -->

TrueNorth-AI's PostgreSQL schema is minimal by design — OpenMRS remains the source of truth for all clinical data. The local database stores only what's needed for the agent's operation:

| Table                   | Purpose                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `patients`              | Maps OpenMRS patient ID to WhatsApp phone + web email. Tracks channel linking status, preferences, reminder settings        |
| `otp_tokens`            | Short-lived verification codes for WhatsApp linking and web login                                                           |
| `refresh_tokens`        | Server-side JWT refresh token state with rotation chain and reuse detection                                                 |
| `conversation_sessions` | LangGraph thread metadata — active flow, last activity. Graph state itself is persisted by LangGraph's `AsyncPostgresSaver` |
| `appointment_records`   | Mirror of OpenMRS appointments with TrueNorth-AI metadata (source, reminder status)                                         |
| `reminder_schedules`    | Each reminder event to send — trigger time, channel, template, delivery status                                              |
| `report_delivery_log`   | Deduplication + tracking for lab result and prescription explanations                                                       |

---

## Monitoring & Observability

<!-- TODO: Add Grafana dashboard screenshot -->
<!-- <p align="center">
  <img src="docs/assets/grafana-dashboard.png" alt="Grafana Dashboard" width="800" />
</p> -->

**LangSmith** traces every LangGraph execution: node-by-node inputs/outputs, LLM prompt-response pairs, token counts, latencies, tool call results, and error traces. Every agent decision is auditable.

**Prometheus + Grafana** tracks infrastructure: API request rates, latency percentiles (p50/p95/p99), active SSE connections, reminder delivery success rates, and background worker health.

---

## Testing Strategy

| Layer                | Approach                                                                                                                                                      |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Tests           | LangGraph node logic (mocked LLM + services), OTP verification, message parsing, reminder scanner                                                             |
| Integration Tests    | FastAPI endpoints against test PostgreSQL, LangGraph execution against local OpenMRS, ActiveMQ event → handler → DB state                                     |
| LLM Evaluation Suite | Intent classification accuracy (>90% on 50-case test set), triage urgency precision/recall, report explanation quality via LLM judge, RAG retrieval relevance |

---

## Roadmap

### MVP (Building Now)

- [x] System architecture & PRD
- [ ] LangGraph agent orchestrator with intent classification and subgraph routing
- [ ] OpenMRS MCP Server with appointment and patient tools
- [ ] Doctor discovery & appointment booking (WhatsApp + Web)
- [ ] Symptom pre-screening & triage routing
- [ ] Medical report & prescription interpretation (event-driven)
- [ ] Proactive reminders (APScheduler + WhatsApp templates)
- [ ] Live queue tracking

### Post-MVP

- [ ] Medication adherence tracking
- [ ] Family/dependent management
- [ ] Multi-language support (Kinyarwanda, French, Swahili)
- [ ] Doctor-side dashboard
- [ ] Health trends & insights from historical lab data
- [ ] Appointment rescheduling with conflict resolution
- [ ] CI/CD pipeline (GitHub Actions → ECR)
- [ ] AWS production deployment (ECS Fargate + RDS)

---

## License

This project is for portfolio and educational purposes.

---

## Acknowledgments

Built with [OpenMRS](https://openmrs.org/) and [Bahmni](https://www.bahmni.org/) — open-source EMR systems powering healthcare delivery across the developing world.

---

<p align="center">
  <sub>Designed and built by <strong>Alain Mugisha</strong> — Software Architect & AI Engineer</sub>
</p>
