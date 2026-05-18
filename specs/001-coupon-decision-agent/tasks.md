# Tasks: 优惠券运营决策 Agent 系统

**Input**: Design documents from `/specs/001-coupon-decision-agent/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests included for critical paths (Agent decision, approval callback, data cleaning) as recommended in spec.md and plan.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Infrastructure)

**Purpose**: Project initialization and basic structure (已部分完成，需补全缺失项)

### 1.1 Environment & Configuration

- [x] T001 Update `.env` with DeepSeek API credentials (LLM_API_KEY, LLM_ENDPOINT, LLM_MODEL)
- [x] T002 Update `app/core/config.py` to add LLM integration settings (llm_api_key, llm_endpoint, llm_model)
- [x] T003 [P] Add API Token validation middleware in `app/middleware/auth.py`
- [ ] T004 [P] Add飞书 signature validation middleware in `app/middleware/feishu_auth.py` (跳过：飞书相关)

### 1.2 Database Migrations (Staging/Feature/Application layers)

- [x] T005 Create Alembic migration: `alembic/versions/create_staging_events.py` (coupon_receipt_event, consumption_event tables in staging schema)
- [x] T006 Create Alembic migration: `alembic/versions/create_feature_metrics.py` (merchant_metrics, user_metrics, coupon_metrics tables in feature schema)
- [x] T007 Create Alembic migration: `alembic/versions/create_application_tables.py` (decision_case, recommendation, action_execution, approval_log in application schema)
- [x] T008 Create Alembic migration: `alembic/versions/create_indexes.py` (add indexes per data-model.md)

### 1.3 Domain Models (SQLAlchemy ORM)

- [x] T009 [P] Create `app/domain/staging/__init__.py` and `app/domain/staging/coupon_receipt_event.py` (model definition)
- [x] T010 [P] Create `app/domain/staging/consumption_event.py` (model definition)
- [x] T011 [P] Create `app/domain/feature/__init__.py` and `app/domain/feature/merchant_metrics.py` (model definition)
- [x] T012 [P] Create `app/domain/feature/user_metrics.py` (model definition)
- [x] T013 [P] Create `app/domain/feature/coupon_metrics.py` (model definition)
- [x] T014 [P] Create `app/domain/application/__init__.py` and `app/domain/application/decision_case.py` (model with state transitions)
- [x] T015 [P] Create `app/domain/application/recommendation.py` (model with JSONB fields)
- [x] T016 [P] Create `app/domain/application/action_execution.py` (model definition)
- [x] T017 [P] Create `app/domain/application/approval_log.py` (model definition)

### 1.4 Pydantic Schemas (API request/response)

- [x] T018 [P] Create `app/schemas/metrics.py` (MerchantMetricsResponse, UserMetricsResponse, CouponMetricsResponse)
- [x] T019 [P] Create `app/schemas/cases.py` (DecisionCaseResponse, DecisionCaseDetailResponse)
- [x] T020 [P] Create `app/schemas/approvals.py` (ApprovalCallbackRequest, ApprovalCallbackResponse)
- [x] T021 [P] Create `app/schemas/rules.py` (RuleScanRequest, RuleScanResponse)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 数据层和ML模型，所有User Stories依赖此阶段完成

**Independent Test**: 导入数据后，Feature层指标计算完成，ML模型AUC ≥ 0.68

### 2.1 Data Cleaning (Raw → Staging)

- [x] T022 Create `app/services/data_cleaning_service.py` (transform raw.offline_train to staging events)
- [x] T023 Implement `transform_to_coupon_receipt_event()` in `app/services/data_cleaning_service.py` (领券事件清洗逻辑)
- [x] T024 Implement `transform_to_consumption_event()` in `app/services/data_cleaning_service.py` (消费事件清洗逻辑)
- [x] T025 Create Celery task: `app/tasks/clean_data.py` (异步执行数据清洗)
- [x] T026 Add `clean_data_task` to `app/tasks/celery_app.conf.include` list
- [x] T027 Write integration test: `tests/integration/test_data_cleaning.py` (验证清洗后事件表数据完整性)

### 2.2 Feature Engineering (Staging → Feature)

- [x] T028 Create `app/features/__init__.py` and `app/features/merchant_features.py` (商户维度聚合逻辑)
- [x] T029 Implement `calculate_merchant_metrics()` in `app/features/merchant_features.py` (7日/30日核销率、变化幅度、折扣深度)
- [x] T030 [P] Create `app/features/user_features.py` (用户维度聚合逻辑)
- [x] T031 [P] Implement `calculate_user_metrics()` in `app/features/user_features.py`
- [x] T032 [P] Create `app/features/coupon_features.py` (优惠券维度聚合逻辑)
- [x] T033 [P] Implement `calculate_coupon_metrics()` in `app/features/coupon_features.py`
- [x] T034 Update `app/tasks/refresh_features.py` (替换placeholder，调用feature计算逻辑)
- [x] T035 Write integration test: `tests/integration/test_feature_calculation.py` (验证聚合指标计算正确性)

### 2.3 ML Model Training (LightGBM)

- [x] T036 Create `app/ml/train/__init__.py` and `app/ml/train/train_model.py` (模型训练脚本)
- [x] T037 Implement feature extraction in `app/ml/train/feature_extractor.py` (用户特征、商户特征、券特征、时间特征)
- [x] T038 Implement time-split validation in `app/ml/train/train_model.py` (1-4月训练、5月验证、6月测试)
- [x] T039 Implement grouped AUC evaluation in `app/ml/train/evaluate_model.py` (按coupon_id分组平均AUC)
- [x] T040 Create `scripts/train_model.py` (命令行入口，调用app.ml.train)
- [x] T041 Save trained model to `app/ml/artifacts/redeem_predictor.joblib` (persist model + feature list)
- [x] T042 Write integration test: `tests/integration/test_model_training.py` (验证AUC ≥ 0.68)

### 2.4 ML Model Inference Service

- [x] T043 Create `app/ml/inference/__init__.py` and `app/ml/inference/predict_service.py`
- [x] T044 Implement `predict_redeem_probability()` in `app/ml/inference/predict_service.py` (加载模型，预测核销概率)
- [x] T045 Update `app/domain/staging/coupon_receipt_event.py` (添加predicted_probability字段，推理后填充)
- [x] T046 Write unit test: `tests/unit/test_predict_service.py` (验证推理输出格式)

---

## Phase 3: User Story 2 - 指标查询API (P1)

**Story Goal**: 分析师查看商户/券/用户多维经营指标，验证计算正确性

**Independent Test**: 导入测试数据后，GET /api/v1/metrics/merchants 返回正确指标，与手工计算一致

### 3.1 Metrics Query APIs

- [ ] T047 [US2] Create `app/api/v1/metrics.py` (FastAPI router for metrics endpoints)
- [ ] T048 [US2] Implement `GET /api/v1/metrics/merchants` in `app/api/v1/metrics.py` (商户指标查询，支持筛选、排序、分页)
- [ ] T049 [US2] [P] Implement `GET /api/v1/metrics/users` in `app/api/v1/metrics.py` (用户指标查询)
- [ ] T050 [US2] [P] Implement `GET /api/v1/metrics/coupons` in `app/api/v1/metrics.py` (优惠券指标查询)
- [ ] T051 [US2] Register metrics router in `app/main.py` (app.include_router(metrics_router))

### 3.2 Repository Layer (Data Access)

- [ ] T052 [US2] Create `app/repositories/__init__.py` and `app/repositories/merchant_metrics_repository.py`
- [ ] T053 [US2] Implement `find_all_with_filters()` in `app/repositories/merchant_metrics_repository.py` (支持筛选、排序、分页)
- [ ] T054 [US2] [P] Create `app/repositories/user_metrics_repository.py` (类似merchant实现)
- [ ] T055 [US2] [P] Create `app/repositories/coupon_metrics_repository.py`

### 3.3 Tests

- [ ] T056 [US2] Write integration test: `tests/integration/test_metrics_api.py` (验证各指标端点响应格式和数据正确性)
- [ ] T057 [US2] Write unit test: `tests/unit/test_merchant_metrics_repository.py` (验证筛选逻辑)

---

## Phase 4: User Story 1 - 审批决策流程 (P1)

**Story Goal**: 运营人员接收异常预警并审批决策，完整闭环

**Independent Test**: 模拟商户核销率下降决策案例，Agent生成建议→推送飞书→审批通过→Mock Action执行

### 4.1 DecisionCase Management

- [ ] T058 [US1] Create `app/repositories/decision_case_repository.py` (CRUD operations)
- [ ] T059 [US1] Implement `create_case()` in `app/repositories/decision_case_repository.py` (创建案例，初始化状态pending)
- [ ] T060 [US1] Implement `update_status()` in `app/repositories/decision_case_repository.py` (状态流转，记录ApprovalLog)
- [ ] T061 [US1] Create `app/services/decision_case_service.py` (业务逻辑层)
- [ ] T062 [US1] Implement `trigger_agent_diagnosis()` in `app/services/decision_case_service.py` (调用Agent决策服务)

### 4.2 Agent Tools (Data Query Tools)

- [ ] T063 [US1] Create `app/agents/tools/__init__.py` and `app/agents/tools/merchant_metrics_tool.py`
- [ ] T064 [US1] Implement `get_merchant_metrics()` tool in `app/agents/tools/merchant_metrics_tool.py` (查询商户指标，返回JSON)
- [ ] T065 [US1] [P] Create `app/agents/tools/coupon_conversion_tool.py` (查询券转化率)
- [ ] T066 [US1] [P] Implement `get_coupon_conversion()` tool in `app/agents/tools/coupon_conversion_tool.py`

### 4.3 DeepSeek LLM Integration

- [ ] T067 [US1] Create `app/integrations/llm/__init__.py` and `app/integrations/llm/deepseek_client.py`
- [ ] T068 [US1] Implement `chat_with_tools()` in `app/integrations/llm/deepseek_client.py` (调用DeepSeek API + Tool Calling)
- [ ] T069 [US1] Implement `validate_json_output()` in `app/integrations/llm/deepseek_client.py` (验证JSON Mode输出格式)
- [ ] T070 [US1] Add retry logic with exponential backoff in `deepseek_client.py` (最多3次重试)
- [ ] T071 [US1] Implement Token usage tracking in `deepseek_client.py` (记录每次调用的prompt_tokens, completion_tokens)

### 4.4 Agent Decision Service

- [ ] T072 [US1] Create `app/agents/__init__.py` and `app/agents/decision_service.py`
- [ ] T073 [US1] Implement `generate_recommendation()` in `app/agents/decision_service.py` (Agent决策主流程)
- [ ] T074 [US1] Define Prompt template in `app/agents/prompts/decision_prompt.py` (明确Agent角色，要求≥3条证据)
- [ ] T075 [US1] Implement `parse_recommendation()` in `app/agents/decision_service.py` (解析LLM输出为Recommendation结构)
- [ ] T076 [US1] Create Celery task: `app/tasks/agent_decision.py` (异步Agent决策任务)
- [ ] T077 [US1] Add `agent_decision_task` to `app/tasks/celery_app.conf.include`

### 4.5 飞书 Approval Integration

- [ ] T078 [US1] Create `app/integrations/feishu/__init__.py` and `app/integrations/feishu/card_builder.py`
- [ ] T079 [US1] Implement `build_approval_card()` in `app/integrations/feishu/card_builder.py` (飞书卡片JSON结构)
- [ ] T080 [US1] Create `app/integrations/feishu/bot_client.py` (飞书机器人API客户端)
- [ ] T081 [US1] Implement `send_approval_card()` in `app/integrations/feishu/bot_client.py` (发送审批卡片给运营人员)
- [ ] T082 [US1] Implement `verify_signature()` in `app/integrations/feishu/signature_validator.py` (HMAC-SHA256验证)

### 4.6 Approval Callback API

- [ ] T083 [US1] Create `app/api/v1/approvals.py` (FastAPI router for approval callback)
- [ ] T084 [US1] Implement `POST /api/v1/approvals/callback` in `app/api/v1/approvals.py` (接收飞书回调)
- [ ] T085 [US1] Validate 飞书 signature in approval callback (使用middleware或手动验证)
- [ ] T086 [US1] Implement approval logic in `app/services/approval_service.py` (记录审批结果，更新DecisionCase状态)
- [ ] T087 [US1] Trigger Mock Action execution if approved in `app/services/approval_service.py`

### 4.7 Mock Action Execution

- [ ] T088 [US1] Create `app/services/mock_action_service.py` (模拟外部系统动作)
- [ ] T089 [US1] Implement `execute_pause_activity()` in `app/services/mock_action_service.py` (暂停活动Mock)
- [ ] T090 [US1] [P] Implement `execute_adjust_discount()` in `app/services/mock_action_service.py` (调整折扣Mock)
- [ ] T091 [US1] [P] Implement `execute_send_coupon()` in `app/services/mock_action_service.py` (发送优惠券Mock)
- [ ] T092 [US1] Create ActionExecution record in `app/repositories/action_execution_repository.py`

### 4.8 DecisionCase Query APIs

- [ ] T093 [US1] Create `app/api/v1/cases.py` (FastAPI router for cases endpoints)
- [ ] T094 [US1] Implement `GET /api/v1/cases` in `app/api/v1/cases.py` (决策案例列表查询，支持筛选)
- [ ] T095 [US1] Implement `GET /api/v1/cases/{case_id}` in `app/api/v1/cases.py` (案例详情，含Recommendation和ApprovalLog)
- [ ] T096 [US1] Register cases router in `app/main.py`

### 4.9 Tests

- [ ] T097 [US1] Write contract test: `tests/contract/test_agent_tools.py` (验证Agent工具输出格式)
- [ ] T098 [US1] Write integration test: `tests/integration/test_agent_decision.py` (验证Agent生成建议流程)
- [ ] T099 [US1] Write integration test: `tests/integration/test_approval_callback.py` (验证飞书回调处理和签名验证)
- [ ] T100 [US1] Write integration test: `tests/integration/test_mock_action.py` (验证Mock Action执行)

---

## Phase 5: User Story 3 - 规则扫描 (P2)

**Story Goal**: 系统自动触发规则扫描生成决策案例

**Independent Test**: 手动调用 POST /api/v1/rules/scan，验证满足条件的商户生成DecisionCase并触发Agent

### 5.1 Rule Engine Configuration

- [ ] T101 [US3] Create `app/rules/__init__.py` and `app/rules/yaml_loader.py`
- [ ] T102 [US3] Create `config/rules/merchant_redeemed_rate_drop.yaml` (商户核销率下降规则)
- [ ] T103 [US3] [P] Create `config/rules/high_discount_low_conversion.yaml` (高折扣低转化规则)
- [ ] T104 [US3] [P] Create `config/rules/user_recall.yaml` (用户召回规则)
- [ ] T105 [US3] Implement `load_rules()` in `app/rules/yaml_loader.py` (解析YAML规则配置)

### 5.2 Rule Scanner

- [ ] T106 [US3] Create `app/rules/scanner.py` (规则扫描执行引擎)
- [ ] T107 [US3] Implement `scan_merchant_rules()` in `app/rules/scanner.py` (扫描商户指标，匹配阈值)
- [ ] T108 [US3] Implement `create_decision_cases()` in `app/rules/scanner.py` (为匹配的商户创建DecisionCase)
- [ ] T109 [US3] Create Celery task: `app/tasks/rule_scan.py` (异步规则扫描任务)
- [ ] T110 [US3] Add `rule_scan_task` to `app/tasks/celery_app.conf.include`
- [ ] T111 [US3] Configure Celery Beat schedule for daily rule scan in `app/tasks/celery_app.py`

### 5.3 Rule Scan API

- [ ] T112 [US3] Create `app/api/v1/rules.py` (FastAPI router for rules endpoints)
- [ ] T113 [US3] Implement `POST /api/v1/rules/scan` in `app/api/v1/rules.py` (手动触发扫描，支持dry_run模式)
- [ ] T114 [US3] Register rules router in `app/main.py`

### 5.4 Tests

- [ ] T115 [US3] Write unit test: `tests/unit/test_yaml_loader.py` (验证规则解析逻辑)
- [ ] T116 [US3] Write integration test: `tests/integration/test_rule_scan.py` (验证规则扫描和DecisionCase创建)

---

## Phase 6: User Story 4 - 案例检索 (P3)

**Story Goal**: 历史决策案例检索与复盘

**Independent Test**: 创建若干测试案例，GET /api/v1/cases 按商户ID搜索返回所有相关案例

### 6.1 Search & Filter Enhancement

- [ ] T117 [US4] Enhance `GET /api/v1/cases` query logic in `app/api/v1/cases.py` (添加created_after, created_before时间筛选)
- [ ] T118 [US4] Implement `search_by_merchant()` in `app/repositories/decision_case_repository.py` (按商户ID高效检索)
- [ ] T119 [US4] Add composite index in `alembic/versions/create_indexes.py` for decision_case (merchant_id, created_at)

### 6.2 Approval History Display

- [ ] T120 [US4] Enhance `GET /api/v1/cases/{case_id}` in `app/api/v1/cases.py` (返回完整ApprovalLog链路)
- [ ] T121 [US4] Implement `get_approval_history()` in `app/repositories/approval_log_repository.py` (按时间排序审批记录)

### 6.3 Tests

- [ ] T122 [US4] Write integration test: `tests/integration/test_case_search.py` (验证检索和筛选逻辑)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 测试覆盖率、文档、性能优化

### 7.1 Test Coverage

- [ ] T123 Generate test coverage report with pytest-cov (目标: 80%+ coverage)
- [ ] T124 Fill missing tests for critical paths (Agent decision, approval callback, data cleaning)

### 7.2 Documentation

- [ ] T125 [P] Update `README.md` with project overview and setup instructions
- [ ] T126 [P] Generate API documentation with FastAPI Swagger/ReDoc (自动生成，需验证端点描述完整)

### 7.3 Performance Optimization

- [ ] T127 Add database connection pool tuning in `app/core/database.py` (pool_size=10, max_overflow=20)
- [ ] T128 Optimize Feature layer queries with EXPLAIN analysis (添加缺失索引)
- [ ] T129 Benchmark API response time (验证<2s response time with 5 concurrent users)

---

## Dependencies & Execution Order

### User Story Completion Order

**Recommended execution sequence**:

1. **Phase 1 (Setup)** - MUST complete first (基础设施)
2. **Phase 2 (Foundational)** - MUST complete before US1/US2 (数据层和ML模型)
3. **Phase 3 (US2)** - 可与 Phase 4 并行执行 (指标查询API)
4. **Phase 4 (US1)** - 核心价值，优先完成 (审批决策闭环)
5. **Phase 5 (US3)** - 依赖 US1 (规则扫描触发Agent)
6. **Phase 6 (US4)** - 依赖 US1 (历史案例复盘)
7. **Phase 7 (Polish)** - 最后完成 (测试和优化)

**Critical dependency**: Phase 2 MUST complete before US1 and US2 (Feature层指标计算是所有后续功能的基础)

### Parallel Execution Opportunities

**Within Phase 1 (Setup)**:
- T009-T017: Domain models可并行编写（不同文件）
- T018-T021: Pydantic schemas可并行编写

**Within Phase 2 (Foundational)**:
- T030-T033: User和Coupon特征计算可并行（不同文件）

**Within Phase 3 (US2)**:
- T049-T050: Users和Coupons API端点可并行实现

**Within Phase 4 (US1)**:
- T065-T066: Coupon conversion tool可并行编写
- T090-T091: Mock actions可并行实现

**Within Phase 5 (US3)**:
- T103-T104: YAML规则文件可并行编写

**Within Phase 7 (Polish)**:
- T125-T126: 文档任务可并行编写

---

## MVP Scope Recommendation

**Minimum Viable Product (MVP)**:

- **Phase 1**: Setup (基础设施)
- **Phase 2**: Foundational (数据清洗、Feature层、ML模型)
- **Phase 4**: User Story 1 (审批决策闭环 - 核心价值)

**MVP Deliverable**: 运营人员可接收Agent决策建议并通过飞书审批后执行Mock Action，验证完整闭环。

**MVP Skip**:
- Phase 3 (US2 - 指标查询): 可通过数据库直接查询验证
- Phase 5 (US3 - 规则扫描): MVP阶段手动触发Agent决策
- Phase 6 (US4 - 案例检索): MVP阶段案例数量少，检索价值低

---

## Implementation Strategy

### Incremental Delivery

1. **Week 1-2**: Phase 1 + Phase 2 (基础设施和数据层)
2. **Week 3-4**: Phase 4 (User Story 1 - MVP核心功能)
3. **Week 5**: Phase 3 + Phase 7 (指标查询API + 测试优化)
4. **Week 6**: Phase 5 + Phase 6 (规则扫描 + 案例检索)

### Test Strategy

- **Critical paths**: Agent decision, approval callback, data cleaning (integration tests)
- **Contract tests**: Agent tools, LLM output format validation
- **Unit tests**: Repository层筛选逻辑, Service层业务逻辑
- **Coverage target**: 80%+ (优先Agent、审批回调、数据清洗)

---

## Total Task Count

- **Setup Phase**: 21 tasks
- **Foundational Phase**: 25 tasks
- **US2 Phase**: 11 tasks
- **US1 Phase**: 43 tasks
- **US3 Phase**: 16 tasks
- **US4 Phase**: 6 tasks
- **Polish Phase**: 7 tasks

**Total**: 129 tasks

---

## Summary

本任务清单按User Story组织，支持独立实施和测试。MVP聚焦US1（审批决策闭环），依赖Phase 2（数据层和ML）完成。后续可扩展US2（指标查询）、US3（规则扫描）、US4（案例检索）。测试覆盖Agent决策、审批回调、数据清洗关键路径，目标80%+覆盖率。
