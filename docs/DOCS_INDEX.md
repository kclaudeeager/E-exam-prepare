# E-exam-prepare Documentation Index

> All documentation lives in the `docs/` directory. The only Markdown file at the project root is `README.md`.

---

## Quick Navigation

### First-Time Setup
Start here → **[SETUP_GUIDE.md](SETUP_GUIDE.md)**

### Understanding the System
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design, service topology, data flows
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** — Full implementation status
- **[COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md)** — Feature-level checklist

### RAG Engine
- **[RAG_INTEGRATION.md](RAG_INTEGRATION.md)** — RAG service API endpoints and frontend integration
- **[PROVIDER_SETUP.md](PROVIDER_SETUP.md)** — LLM provider switching (Groq / Gemini / OpenAI)
- **[GROQ_SETUP.md](GROQ_SETUP.md)** — Groq-specific configuration and troubleshooting

### API and Database
- **[API_REFERENCE.md](API_REFERENCE.md)** — Full REST API reference
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** — Database migration and deployment guide

### Frontend
- **[DEVELOPMENT.md](DEVELOPMENT.md)** — Frontend dev setup, structure, patterns
- **[INTEGRATION.md](INTEGRATION.md)** — Frontend to Backend API integration guide

### Change History
- **[FEATURES_ADDED_Feb24.md](FEATURES_ADDED_Feb24.md)** — Advanced features (role-based docs, sharing, adaptive learning)
- **[GROQ_INTEGRATION.md](GROQ_INTEGRATION.md)** — Groq integration overview
- **[GROQ_CHANGES.md](GROQ_CHANGES.md)** — Technical diff of Groq changes
- **[GROQ_COMPLETE.md](GROQ_COMPLETE.md)** — Groq completion status
- **[CUSTOM_PROVIDERS_GUIDE.md](CUSTOM_PROVIDERS_GUIDE.md)** — Custom LLM and embedding provider guide
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** — Advanced features implementation details

---

## Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | End-to-end setup (local and Docker) | New developers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, service topology, data flows | All developers |
| [API_REFERENCE.md](API_REFERENCE.md) | REST API endpoints with request/response examples | Frontend / API consumers |
| [RAG_INTEGRATION.md](RAG_INTEGRATION.md) | RAG service endpoints and query patterns | Backend / RAG developers |
| [PROVIDER_SETUP.md](PROVIDER_SETUP.md) | Switching between Groq, Gemini, OpenAI | DevOps / RAG developers |
| [GROQ_SETUP.md](GROQ_SETUP.md) | Groq-specific config, models, troubleshooting | RAG developers |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Frontend project structure and dev workflow | Frontend developers |
| [INTEGRATION.md](INTEGRATION.md) | Frontend to Backend data flows and patterns | Full-stack developers |
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Database migrations and deployment checklist | DevOps / Backend |
| [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md) | Feature completion tracking | Project managers |

---

## By Use Case

### "I just want to get it running"
1. Read [SETUP_GUIDE.md](SETUP_GUIDE.md) - Quick Start section
2. Run `make docker-up` (Docker) or `make dev-all` (local)
3. Open http://localhost:3000

### "I want to understand the architecture"
1. [ARCHITECTURE.md](ARCHITECTURE.md) - service topology and data flows
2. [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) - what is built

### "I need to switch LLM providers"
1. [PROVIDER_SETUP.md](PROVIDER_SETUP.md) - compare Groq / Gemini / OpenAI
2. Change `LLAMA_INDEX_PROVIDER` in `.env`
3. Restart RAG service

### "I'm working on the frontend"
1. [DEVELOPMENT.md](DEVELOPMENT.md) - setup, structure, patterns
2. [INTEGRATION.md](INTEGRATION.md) - API data flows
3. [API_REFERENCE.md](API_REFERENCE.md) - endpoint details

### "I'm deploying to production"
1. [SETUP_GUIDE.md](SETUP_GUIDE.md) - Docker Compose section
2. [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - database setup
3. Ensure all `.env` variables are set
