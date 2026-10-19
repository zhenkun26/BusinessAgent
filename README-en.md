# BusinessAgent · Zhiduoxing

A multi-agent platform for enterprise knowledge and business workflows, bringing retrieval, data analysis, and business operations into a shared natural-language workflow.

[简体中文](README.md) | **English**

[Quick start](#quick-start) · [Architecture](#architecture) · [Documentation](#documentation)

[![CI](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](enterprise-agent/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

A business request can involve checking a policy, retrieving data, and performing an operation.
BusinessAgent uses a Planner to break requests into subtasks, delegates them to specialized agents, and combines their results.

The project covers the path from a natural-language request to business execution:

- For questions, retrieve knowledge accessible to the user and provide source information.
- For analysis, read a snapshot from the CRM provider and calculate and render a deterministic report in Python.
- For business operations, check tool permissions and apply human approval where required.
- When a multistep operation fails, run Saga compensation for supported steps and record the outcome.

The repository includes a backend service, Web interface, evaluation scripts, and deployment configuration.
It is intended for exploring multi-agent orchestration, enterprise RAG, and controlled tool execution.

## Use cases

These examples require the relevant knowledge documents, user roles, and model configuration.
The shipped sample documents and interface are primarily in Chinese; the requests below describe the same scenarios in English.

| Scenario | Example request | Workflow |
| --- | --- | --- |
| Enterprise knowledge Q&A | “What are the company's travel reimbursement rules?” | Retrieve knowledge, compose an answer, and return sources |
| Business data analysis | “Rank customers by their total order value.” | Read an authorized CRM snapshot, aggregate in Python, and render a deterministic report |
| Business record lookup | “Look up customer C001.” | Check role permissions before calling a business tool |
| Business operations | “Create a support ticket for customer C001.” | Extract parameters, check permissions, and call the ticket tool |
| Approval collaboration | “Send a follow-up email to an external customer.” | Create an approval request according to operation rules for an authorized reviewer |
| Combined requests | “Look up the customer and explain the company's after-sales policy.” | Dispatch subtasks to different agents and aggregate the results |

> Business tools default to Mock. Analysis uses the same CRM provider: built-in samples for Mock, controlled snapshot endpoints for HTTP.
> These examples demonstrate workflows. Connecting real business systems requires adapter configuration and integration testing.

## Core capabilities

### Multi-agent orchestration

- A Planner → Agent Executor → Aggregator workflow built with LangGraph.
- Parallel subtask dispatch through the Send API.
- Knowledge, Analysis, and Execution agents with distinct responsibilities.
- Bounded replanning for results that require additional retrieval, with at most 2 extra rounds.

### Knowledge retrieval and answers

- Document loading for Markdown, PDF, DOCX, and TXT.
- Milvus vector retrieval followed by reranking.
- The supplied `.env.example` selects Beijing Bailian `text-embedding-v4` (1024 dimensions) and `qwen3-rerank`; local BGE remains a development option.
- Role and department namespace filtering in the retrieval path.
- Source information, confidence-based decisions, and fallback paths for retrieval failures.

### Controlled business execution

- Tools for customers, orders, CRM tasks, tickets, email, and approval queries.
- RBAC to restrict tool access by role.
- Human approval for operations that require review.
- Saga coordination for multistep execution and supported compensation scenarios.
- An external HTTP adapter layer with timeouts, retries, and audit records.

### State management and observability

- Checkpoints to save conversation state and support recovery.
- Explicit Redis or PostgreSQL checkpoints that fail closed on outages; memory requires an explicit development choice.
- SSE events for execution progress and response text.
- Audit logs, token usage collection, Prometheus metrics, and OpenTelemetry tracing.
- APIs for prompt versioning, knowledge candidate review, and user administration.

## Architecture

The following diagram simplifies the main workflow:

```mermaid
flowchart TD
    U[Web UI / API Client] --> API[FastAPI · Authentication]
    API --> P[Planner]

    P --> K[Knowledge Agent]
    P --> A[Analysis Agent]
    P --> E[Execution Agent]
    P -->|Direct response| G[Aggregator]

    K --> R[RAG · Milvus · Reranker]
    A --> D[CRM Snapshot · Python Aggregation]
    E --> T[Tool Gateway · RBAC]
    T --> H[Approval / Saga / Business Adapters]

    K --> G
    A --> G
    E --> G

    G -->|Replan · max 2 rounds| P
    G --> O[Answer · Sources · Execution Status]
```

| Layer | Main technologies |
| --- | --- |
| API and interaction | FastAPI, Web UI, SSE |
| Agent orchestration | LangGraph, LangChain |
| Model access | DeepSeek Flash by default, Pro for complex tasks; Ollama for development only |
| Retrieval and reranking | Milvus, Beijing Bailian text-embedding-v4, qwen3-rerank |
| Business data and state | PostgreSQL, Redis Stack |
| Security and workflows | JWT, RBAC, human approval, Saga |
| Observability | OpenTelemetry, Prometheus, audit logs |
| Deployment and checks | Docker Compose, Kubernetes manifests, GitHub Actions |

## Quick start

These steps target local development on macOS / Linux.
Infrastructure runs through Docker Compose; the API and Worker run on the host.
The engineering target is isolated single-host Linux Compose. These procedures await runtime acceptance and require separate data, accounts and an API budget; do not apply them to current business environments.

### 1. Prerequisites

- Python 3.11+
- Git
- Docker and Docker Compose
- Separate credentials, access and budget for Beijing Bailian embedding/reranking and DeepSeek
- Model/data/role settings from the [model profile](enterprise-agent/deploy/MODEL_PROFILE.md); verify provider aliases again during real acceptance

The selected profile needs no local model downloads. Legacy BGE/Ollama paths are outside the first production candidate.

### 2. Get the code and install dependencies

```bash
git clone https://github.com/zhenkun26/BusinessAgent.git
cd BusinessAgent/enterprise-agent

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r deploy/requirements-prod.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and review these settings:

| Setting | Purpose |
| --- | --- |
| `MODEL_PROFILE` | Keep `bailian-deepseek-v1` for the selected candidate |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `PRIMARY_LLM_MODEL`, `LITE_LLM_MODEL` | DeepSeek credentials and profile-defined model names |
| `EMBEDDING_API_KEY`, `RERANKER_API_KEY` | Independent Beijing Bailian credentials; keep endpoints/dimension/collection aligned |
| `POSTGRES_*`, `REDIS_*`, `MILVUS_*` | Match the isolated infrastructure |
| `JWT_SECRET_KEY`, `AUTH_REQUIRE_PASSWORD`, `AUTH_CHECK_DB` | Random secret; password and database identity checks enabled |
| `TOOL_PROVIDER`, `CRM_TOOL_PROVIDER` | Mock for initial synthetic data; explicitly configure HTTP reference services separately |
| `MODEL_STARTUP_PROBES_ENABLED` | False initially; production startup refuses until paid probes are explicitly authorized |

Do not commit credentials from `.env`. The selected profile uses external models. Optional
local ML experiments use the separately declared `deploy/requirements-ml.txt`; they are not
required for this candidate. See the [deployment guide](enterprise-agent/deploy/DEPLOY.md)
for the immutable image, explicit migration and production configuration.

### 4. Start infrastructure

```bash
docker compose up -d etcd minio milvus-standalone postgres redis
docker compose ps
```

Wait for readiness. PostgreSQL no longer auto-runs application initialization SQL. Explicitly migrate to schema v7, check status and bootstrap an administrator before starting the application. Use the [database guide](enterprise-agent/deploy/DATABASE_BOOTSTRAP.md); legacy adoption is allowed only on an authorized isolated copy.

`python -B -m app.core.db_bootstrap plan` is an offline preview. Real PostgreSQL/API/Linux and model acceptance remain BLOCKED; model calls and ingestion require separate authorization.

### 5. Import sample knowledge and start services

Use the authorized upload/review/publication flow in the [knowledge publication contract](docs/50-engineering/knowledge-publication.md), with `eval/sample_docs/财务报销制度.md` as a synthetic input. Historical direct ingestion commands do not establish current publication visibility. Real ingestion calls external models and writes stores; it has not been executed for this candidate.

Start the API:

```bash
python -m app.main
```

In another terminal, enter `enterprise-agent/`, activate the same virtual environment,
and start the background Worker:

```bash
python -m app.worker
```

The Worker handles background tasks, including document ingestion, approval timeouts, and compensation retries.

### 6. Open the application

| Entry point | URL |
| --- | --- |
| Web interface | http://localhost:8000/ui/ |
| API documentation | http://localhost:8000/docs |
| API liveness | http://localhost:8000/health |
| Dependency status | http://localhost:8000/ready |
| Prometheus metrics | http://localhost:8000/metrics |

Sign in with an explicitly bootstrapped account; `/me` verifies its current role. There is no default password or role-based login bypass. Try this question against the Chinese sample policy:

> 公司的差旅报销有哪些规定？

This asks for the company's travel reimbursement rules.
Then use a role with order-query permission to try:

> 统计所有客户的订单总额。

This asks for total order value across customers.

`/health` checks whether the API is alive. Complete functionality also depends on databases,
retrieval services, models, and their configuration.

## Verification and tests

From the repository root, use the reviewed offline inventory:

```bash
python3 -I -B enterprise-agent/scripts/final_candidate.py
# Explicitly run reviewed entries and retain a fresh receipt:
python3 -I -B enterprise-agent/scripts/final_candidate.py --execute --record candidate-001
```

See [verification scope and side effects](docs/50-engineering/final-candidate-verification.md).
The executed sweep returns 2 while real gates remain BLOCKED. Full pytest/plugins and
historical W5–W9 scripts require separate dependency and side-effect review; the fixed
inventory does not claim to cover every test or real service. Never infer current acceptance
from historical CI results or the `main` badge above. Candidate-specific PR/CI evidence and
remaining gates are recorded in the [delivery status](docs/50-engineering/delivery-status.md).

## Current status and limitations

Core agent workflows, RAG, permission checks, approvals, compensation, and the Web interface are implemented.
The repository also contains automated tests, technical verification, and delivery records.

Current boundaries:

- Analysis follows the CRM provider with bounded snapshots and deterministic reports; real HTTP analytics acceptance remains BLOCKED.
- Business tools default to Mock mode. Adapter code alone does not establish acceptance against real systems.
- Real CRM, email, and SSO integration still requires interface contracts, test environments, and integration evidence.
- Formal UAT, security acceptance against real systems, staged rollout, and production approval remain incomplete.
- Only independent subtasks run in parallel; identified dependencies are rejected. General DAG scheduling, multitenancy and long-term memory are outside this candidate.
- Checkpoints do not automatically fall back. Two-process persistence and lease-expiry write fencing remain unresolved acceptance gates.
- Single-organization, single-host Linux Compose is the target; Kubernetes/multihost HA, measured capacity and production readiness are not accepted claims.
- The source version remains 1.3.0 with unreleased changes; commit/image/schema identities must be recorded separately. All L/D/O/B/S/R runtime matrices and full RAG remain BLOCKED.

See the [ROADMAP](docs/40-process/ROADMAP.md) for detailed progress and outstanding work.

## Repository structure

```text
BusinessAgent/
├── README.md               # Chinese introduction and canonical navigation
├── README-en.md            # English translation
├── enterprise-agent/
│   ├── app/
│   │   ├── agents/          # Knowledge, Analysis, Execution
│   │   ├── graph/           # Planning, dispatch, aggregation, checkpoints
│   │   ├── rag/             # Ingestion, retrieval, reranking, fallback
│   │   ├── tools/           # Business tools, HTTP adapters, Saga
│   │   ├── api/             # Chat, authentication, approval, administration
│   │   ├── security/        # JWT and RBAC
│   │   ├── observability/   # Audit, tracing, metrics, token usage
│   │   └── static/          # Web interface
│   ├── tests/              # Automated tests
│   ├── eval/               # Evaluation scripts and sample documents
│   └── deploy/             # Deployment, database and monitoring configuration
├── docs/                   # Product, operations and engineering documentation
├── openspec/               # Specifications and change records
└── interview/              # Presentation and interview materials
```

## Documentation

The detailed project documentation below is primarily in Simplified Chinese.

| Topic | Entry point |
| --- | --- |
| Complete repository index | [contents](contents.md) |
| Product proposal | [Enterprise knowledge workflow Agent proposal](docs/10-product-plan/企业知识工作流Agent产品方案_v3_整合版.md) |
| Product features and design | [Product documentation](docs/20-product/产品文档.md) |
| Web interface usage | [User guide](docs/30-guides/产品使用手册-前端版.md) |
| Scenarios and examples | [Use case guide](docs/30-guides/使用案例手册.md) |
| Operations and troubleshooting | [Operations guide](docs/30-guides/运维维护手册.md) |
| Deployment configuration | [Deployment guide](enterprise-agent/deploy/DEPLOY.md) |
| Sample knowledge documents | [sample_docs](enterprise-agent/eval/sample_docs/) |
| Development progress | [ROADMAP](docs/40-process/ROADMAP.md) |
| Design decisions | [DECISIONS](docs/40-process/DECISIONS.md) |
| Known issues | [ISSUES](docs/40-process/ISSUES.md) |
| Version history | [CHANGELOG](CHANGELOG.md) |
| Presentation and interview materials | [Presentation page](interview/产品介绍网页/index.html) · [Interview notes](interview/Agent项目面试备稿.md) |

## Feedback and contributions

Use [GitHub Issues](https://github.com/zhenkun26/BusinessAgent/issues) to report problems or discuss improvements.
Include reproduction steps, expected behavior, actual behavior, and sanitized environment details.

Before contributing, read [AGENTS.md](AGENTS.md) and the
[project change workflow](openspec/specs/openspec-normalization/spec.md),
and run the checks relevant to your changes.

## License

[MIT](LICENSE)
