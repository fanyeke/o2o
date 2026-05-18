# Research: 优惠券运营决策 Agent 系统

**Feature**: 001-coupon-decision-agent | **Date**: 2026-05-17

## Overview

本文档记录关键技术决策、最佳实践调研和替代方案评估，支撑 Implementation Plan 的技术栈选择。

---

## 1. 数据架构：三层数据仓库模式

### Decision: 采用 Raw → Staging → Feature 三层架构

**Rationale**:
- 天池数据集为原始CSV文件，需要清洗和转换
- 分层架构便于数据质量监控和回溯
- Feature层聚合指标支持快速查询和规则扫描
- PostgreSQL支持JSONB存储Agent证据，无需额外NoSQL

**Alternatives Considered**:
- **方案A**: 单表存储（直接查询原始CSV）- 拒绝理由：性能差，无法支持聚合指标计算
- **方案B**: 使用数据湖（S3 + Spark）- 拒绝理由：过度复杂，MVP阶段无需大数据技术栈
- **方案C**: 使用时序数据库（TimescaleDB）- 拒绝理由：指标计算主要按商户/券维度聚合，非纯时序场景

**Best Practices**:
- Raw层：保持原始数据不变，仅做类型转换（STRING → TIMESTAMP）
- Staging层：清洗为事件表（领券事件、消费事件），建立索引（user_id, merchant_id, date_received）
- Feature层：使用物化视图或定时刷新表存储聚合指标，避免每次查询重新计算

---

## 2. ML模型：LightGBM核销预测

### Decision: 使用LightGBM + 时间切分验证

**Rationale**:
- LightGBM在天池O2O竞赛中被验证有效（基线AUC 0.68+）
- 支持分类特征（merchant_id, coupon_id）无需编码
- 时间切分（1-4月训练、5月验证、6月测试）避免数据泄漏
- 模型文件小（<10MB），推理速度快（<100ms）

**Alternatives Considered**:
- **方案A**: XGBoost - 拒绝理由：LightGBM训练速度更快，内存占用更低
- **方案B**: 深度学习（DeepFM）- 拒绝理由：过度复杂，数据集规模小（26万条）不适合深度模型
- **方案C**: 逻辑回归基线 - 拒绝理由：特征交互复杂，线性模型表现差

**Best Practices**:
- 特征工程：用户历史核销率、商户核销率、券折扣深度、距离特征、时间特征（领券星期几、月份）
- 分组AUC评估：按coupon_id分组计算平均AUC（竞赛标准）
- 模型持久化：joblib保存模型和特征列表

---

## 3. Agent系统：DeepSeek Tool Calling

### Decision: 使用DeepSeek API + JSON Mode + Tool Calling

**Rationale**:
- DeepSeek v4-flash成本低（约为GPT-4的1/10），响应速度快（<5s）
- JSON Mode确保输出结构化格式（证据列表、建议动作）
- Tool Calling支持Agent调用数据查询工具（商户指标查询、券转化率查询）
- 用户已提供API Key和endpoint配置

**Alternatives Considered**:
- **方案A**: OpenAI GPT-4 - 拒绝理由：成本高，MVP阶段预算有限
- **方案B**: 本地部署Llama 3 - 拒绝理由：需要GPU资源，Tool Calling支持不成熟
- **方案C**: Anthropic Claude - 拒绝理由：成本中等，但Tool Calling生态不如OpenAI成熟

**Best Practices**:
- Prompt工程：明确Agent角色（"优惠券运营决策专家"），提供业务背景，要求输出≥3条证据
- Tool定义：2个核心工具（get_merchant_metrics, get_coupon_conversion）
- JSON Schema：定义Recommendation结构（evidence_list, suggested_actions, risk_alerts, confidence_score）
- 降级策略：重试3次（5s、10s、20s间隔），失败标记"诊断失败"

---

## 4. 异步任务：Celery + Redis

### Decision: Celery + Redis broker + Celery Beat定时任务

**Rationale**:
- 已有Celery配置（app/tasks/celery_app.py）
- 支持定时任务（特征刷新、规则扫描）
- Redis既是broker也是backend，简化部署
- 任务失败自动重试，支持进度追踪

**Alternatives Considered**:
- **方案A**: RQ (Redis Queue) - 拒绝理由：不支持定时任务，需要额外调度器
- **方案B**: Django Background Tasks - 拒绝理由：依赖Django，项目使用FastAPI
- **方案C**: Kubernetes CronJob - 拒绝理由：过度复杂，需要K8s集群

**Best Practices**:
- 任务设计：每个任务独立幂等，避免长时间阻塞（特征计算分批处理）
- 错误处理：max_retries=3, retry_delay指数增长（5s、10s、20s）
- 监控：使用Celery Flower或基础日志记录任务状态

---

## 5. 认证：飞书OAuth + API Token混合模式

### Decision: 飞书OAuth用于审批，API Token用于Dashboard

**Rationale**:
- 飞书审批卡片需要飞书身份验证（无缝集成）
- Dashboard访问不依赖飞书账号，便于分析师和管理员独立使用
- 实现简单，无需自建账号体系
- API Token易于管理和轮换

**Alternatives Considered**:
- **方案A**: 单一飞书OAuth - 拒绝理由：Dashboard用户可能不使用飞书
- **方案B**: 自建账号体系 - 拒绝理由：过度复杂，MVP阶段优先集成现有工具
- **方案C**: 无认证 - 拒绝理由：安全问题，审批数据敏感

**Best Practices**:
- 飞书OAuth：使用飞书开放平台OAuth2.0，回调接口验证签名
- API Token：使用JWT或简单Token（存储在环境变量或配置文件）
- 权限控制：运营人员（审批）、分析师（查看）、管理员（配置）

---

## 6. 前端Dashboard：可选方案

### Decision: MVP阶段暂不实现前端，依赖飞书审批卡片

**Rationale**:
- 核心交互通过飞书审批卡片完成（User Story 1）
- Dashboard为P2功能（User Story 2），可在Agent验证后逐步实现
- 前端技术栈选择影响开发周期（React/Vue需要额外团队或学习成本）
- REST API已提供查询能力，可先用飞书卡片或简单HTML模板

**Alternatives Considered**:
- **方案A**: React + Ant Design - 拒绝理由：需要前端开发经验，MVP周期延长
- **方案B**: FastAPI Jinja2模板 - 拒绝理由：可用但非长期方案，后续可能替换
- **方案C**: Streamlit快速原型 - 拒绝理由：适合数据科学原型，不适合生产审批系统

**Best Practices**（如果后续实现）:
- 使用React/Vue构建单页应用
- 图表库：Recharts或ECharts（核销率趋势图）
- 筛选器：Ant Design或Material-UI组件
- API调用：使用axios或fetch，Token认证

---

## 7. 飞书集成：审批卡片 + 回调接口

### Decision: 飞书机器人发送审批卡片，FastAPI接收回调

**Rationale**:
- 飞书审批卡片支持交互式按钮（批准/驳回）
- 回调接口接收审批结果，验证签名确保可信
- 卡片内容包含Agent建议详情（证据列表、风险提示）
- 避免自定义审批界面开发

**Alternatives Considered**:
- **方案A**: 飞书Webhook推送文本消息 - 拒绝理由：无法支持交互式审批
- **方案B**: 飞书小程序 - 拒绝理由：开发复杂，需要飞书IDE和小程序审核
- **方案C**: 邮件审批 - 拒绝理由：体验差，无法实时交互

**Best Practices**:
- 卡片模板：使用飞书卡片JSON Schema，包含案例ID、Agent建议摘要、审批按钮
- 签名验证：使用飞书开放平台提供的签名算法（HMAC-SHA256）
- 回调处理：异步记录审批结果，触发Mock Action执行

---

## 8. 数据库迁移：Alembic

### Decision: 使用Alembic管理数据库版本

**Rationale**:
- 已有Alembic配置和初始迁移（84a9ab83bcf4_create_raw_tables.py）
- 支持增量迁移（Staging层、Feature层、Application层）
- 版本追踪便于回滚和团队协作

**Alternatives Considered**:
- **方案A**: 手动SQL脚本 - 拒绝理由：无版本控制，易出错
- **方案B**: Django migrations - 拒绝理由：依赖Django ORM，项目使用SQLAlchemy

**Best Practices**:
- 迁移命名：描述性名称（create_staging_events, create_feature_metrics）
- 数据迁移：避免在迁移脚本中执行大量数据转换（使用Celery任务）
- 测试：迁移前后验证数据完整性

---

## 9. 性能优化策略

### Decision: 物化视图 + 索引 + 分批处理

**Rationale**:
- Feature层聚合指标查询频繁（规则扫描、Dashboard）
- 物化视图避免每次查询重新计算聚合（7日/30日核销率）
- 索引优化user_id、merchant_id、date_received查询
- 分批处理避免单次特征计算阻塞（按商户分批）

**Alternatives Considered**:
- **方案A**: 缓存层（Redis）- 拒绝理由：数据一致性复杂，PostgreSQL物化视图更直接
- **方案B**: 预计算所有指标 - 拒绝理由：灵活性差，无法支持时间窗口变化

**Best Practices**:
- 物化视图：每日刷新（Celery Beat触发）
- 索引：user_id、merchant_id、date_received、coupon_id复合索引
- 查询优化：使用EXPLAIN分析慢查询，添加WHERE条件索引

---

## 10. 测试策略

### Decision: pytest + TDD优先路径（Agent核心逻辑）

**Rationale**:
- 已有pytest配置和基础测试（test_health.py、test_config.py）
- Agent决策逻辑为关键路径，TDD确保正确性
- API测试使用httpx异步客户端
- 集成测试覆盖完整链路（规则扫描→Agent→审批→Mock Action）

**Alternatives Considered**:
- **方案A**: unittest - 拒绝理由：pytest生态更好，支持async测试
- **方案B**: 无TDD - 拒绝理由：关键路径风险高，测试覆盖率要求80%+

**Best Practices**:
- 单元测试：Repository、Service层逻辑
- 集成测试：API端点、Celery任务
- Contract测试：Agent工具调用和LLM输出格式
- Coverage目标：80%+（优先Agent、审批回调、数据清洗）

---

## 11. 监控与日志

### Decision: 结构化日志 + Token使用量统计

**Rationale**:
- MVP阶段基础日志即可（app.log + celery.log）
- DeepSeek成本监控必要（每次调用记录Token用量）
- 后续可扩展为Prometheus + Grafana监控

**Alternatives Considered**:
- **方案A**: Prometheus + Grafana - 拒绝理由：过度复杂，MVP阶段优先功能实现
- **方案B**: 无日志 - 拒绝理由：无法排查问题

**Best Practices**:
- 结构化日志：JSON格式，包含timestamp、level、module、message
- Token统计：每次LLM调用记录prompt_tokens、completion_tokens、total_tokens
- 异常日志：记录LLM调用失败、审批回调验证失败、Celery任务失败

---

## 12. Docker部署

### Decision: Docker Compose单机部署

**Rationale**:
- 已有docker-compose.yml配置（PostgreSQL、Redis、API、Worker、Beat）
- MVP阶段无需K8s集群
- 开发环境一致，便于团队协作

**Alternatives Considered**:
- **方案A**: Kubernetes - 拒绝理由：过度复杂，需要运维团队
- **方案B**: 直接部署（systemd）- 拒绝理由：环境不一致，部署复杂

**Best Practices**:
- 服务编排：PostgreSQL（持久化）、Redis（持久化）、API（FastAPI）、Worker（Celery）、Beat（定时任务）
- 健康检查：API使用curl /health，PostgreSQL使用pg_isready
- 数据持久化：PostgreSQL和Redis使用Docker volumes

---

## Summary

所有关键技术决策已明确，无需额外澄清。可直接进入 Phase 1 设计阶段（data-model.md、contracts/、quickstart.md）。
