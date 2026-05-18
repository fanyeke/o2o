# Implementation Plan: 优惠券运营决策 Agent 系统

**Branch**: `001-coupon-decision-agent` | **Date**: 2026-05-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-coupon-decision-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

构建基于天池O2O优惠券数据集的智能决策系统，实现"指标监控→Agent诊断→人工审批→动作执行"闭环。技术方案：FastAPI模块化单体 + PostgreSQL三层数据架构（Raw/Staging/Feature） + LightGBM核销预测 + DeepSeek Agent决策 + Celery异步任务 + 飞书审批集成。数据规模：1-5万商户、10-50万用户、26万领券记录。核心价值：Agent自动生成决策建议（≥3条证据），运营人员审批后执行Mock Action。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI 0.136+, SQLAlchemy 2.0+, Celery 5.4+, PostgreSQL 17, Redis 7, LightGBM 4.0+, DeepSeek API (deepseek-v4-flash), scikit-learn 1.4+, pandas 2.0+
**Storage**: PostgreSQL (JSONB for Agent evidence, materialized views for metrics), Redis (Celery broker/backend)
**Testing**: pytest 8.0+, pytest-asyncio, httpx for API testing
**Target Platform**: Linux server (Docker Compose deployment), supports 5 concurrent users with <2s response time
**Project Type**: Web-service (modular monolith: FastAPI backend + optional frontend dashboard)
**Performance Goals**: 5 concurrent users, <2s API response, Agent decision <30s (incl. DeepSeek API call), feature refresh <30min, ML model AUC ≥0.68
**Constraints**: Basic observability (app logs + Celery logs), DeepSeek cost monitoring (Token usage), approval workflow <3 clicks, Agent ≥3 evidence items per recommendation
**Scale/Scope**: 1-5万 merchants, 10-50万 users, ~26万 coupon receipt records, 8 functional requirements (FR-001 to FR-022), 4 user stories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Project constitution file (`constitution.md`) is template-only. Custom principles to be defined post-MVP based on lessons learned.

**Current Assumptions**:
- ✅ Modular monolith architecture (not premature microservices)
- ✅ TDD workflow recommended but not enforced (existing tests < 80% coverage)
- ✅ Observability: Basic logging only (MVP stage, not production-ready)
- ✅ Security: Mixed authentication (飞书 OAuth + API Token) acceptable for internal tool

**Post-MVP Recommendations**:
- Define constitution after MVP stabilization
- Enforce TDD for critical paths (Agent decision, approval callback)
- Add observability standards (metrics, tracing) before production deployment

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Option 1: Modular Monolith (SELECTED - current implementation)
app/
├── api/                  # REST API endpoints (FastAPI routers)
│   └── v1/
│       ├── health.py     # Health check endpoint
│       ├── datasets.py   # Data import trigger
│       ├── metrics.py    # Metrics query API (to implement)
│       ├── cases.py      # DecisionCase API (to implement)
│       └── approvals.py  # 飞书 callback API (to implement)
├── core/                 # Core infrastructure
│   ├── config.py         # Pydantic Settings
│   ├── database.py       # SQLAlchemy engine
│   └── logging.py        # Logging setup
├── db/                   # Database base models
│   └ base.py
├── domain/               # Domain models (business entities)
│   ├── raw/              # Raw layer: offline_train, offline_test
│   ├── staging/          # Staging layer: events (to implement)
│   └── feature/          # Feature layer: aggregated metrics (to implement)
│   └── application/      # Application layer: DecisionCase, Recommendation, ActionExecution (to implement)
├── features/             # Feature engineering logic (to implement)
├── ml/                   # ML training & inference (to implement)
│   ├── train/            # Model training scripts
│   ├── inference/        # Prediction service
│   └ artifacts/          # Persisted models
├── agents/               # Agent decision logic (to implement)
│   ├── tools/            # Data query tools for Agent
│   ├── prompts/          # Prompt templates
│   └ decision_service.py # Agent orchestration
├── rules/                # Rule engine (to implement)
│   ├── yaml_loader.py    # YAML rule parser
│   ├── scanner.py        # Rule execution engine
├── integrations/         # External service integrations
│   ├── llm/              # LLM clients (DeepSeek, etc.)
│   │   └ deepseek_client.py (to implement)
│   └ feishu/             # 飞书 bot & card (to implement)
├── repositories/         # Data access layer (to implement)
├── services/             # Business service layer (to implement)
├── tasks/                # Celery async tasks
│   ├── celery_app.py     # Celery configuration
│   ├── import_dataset.py # Data import task (implemented)
│   ├── refresh_features.py # Feature refresh (placeholder)
│   ├── agent_decision.py # Agent decision task (to implement)
│   └ rule_scan.py        # Rule scanning task (to implement)
├── schemas/              # Pydantic request/response schemas (to implement)
└── main.py               # FastAPI application entry

tests/
├── integration/          # API endpoint tests
│   └ test_health.py      # Health check test (implemented)
├── unit/                 # Unit tests for services, repositories
│   └ test_config.py      # Config test (implemented)
└── contract/             # Agent contract tests (to implement)

scripts/
├── import_dataset.py     # CSV import script (implemented)
├── train_model.py        # ML training entry (to implement)
└── init_metrics.py       # Initialize feature layer (to implement)

alembic/                  # Database migrations
├── versions/
│   └ 84a9ab83bcf4_create_raw_tables.py (implemented)
├── env.py

data/                     # CSV datasets
├── offline_train.csv     # Training data (71.6 MB)
├── offline_test.csv      # Test data (4.0 MB)
└ Online Retail.xlsx      # Online behavior data (23.7 MB)
```

**Structure Decision**: Modular monolith with clear separation of concerns (domain layers, agents, ML, integrations). Allows future extraction to microservices if needed (Agent service, ML service, 飞书 integration service). Current implementation uses single `app/` directory with sub-modules.

## Complexity Tracking

> **No constitution violations detected - MVP stage, constitution to be defined post-stabilization**
