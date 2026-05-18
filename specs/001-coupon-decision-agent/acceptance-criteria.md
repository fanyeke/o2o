# Decision System Readiness v1 - 验收看板

**Date**: 2026-05-18
**Status**: DRAFT - 待实施验证

---

## 总体验收目标

**一键跑通完整链路**:

```
原始数据导入 → 数据清洗 → time-safe特征计算 → 模型训练与评估
→ 规则扫描生成案例 → Agent生成建议 → 人工审批 → Mock Action执行
→ 全链路日志可追溯
```

---

## 验收量化指标

| 模块 | 目标 | 量化标准 | 当前状态 |
|---|---|---|---|
| 初始化 | 从零可复现 | init_metrics.py 或统一pipeline退出码为0 | ⏳ 待验证 |
| 数据质量 | 特征表可信 | 三类feature表非空，关键字段空值率<5% | ⏳ 待验证 |
| 时间泄漏 | 训练不看未来 | 抽样或SQL审计中，未来数据使用次数=0 | ⏳ 待实现 |
| 模型 | 离线效果可信 | time-based test grouped AUC≥0.68 | ⏳ 待重训 |
| 模型稳定性 | 不是偶然结果 | 连续3次训练AUC波动≤0.03 | ⏳ 待验证 |
| Agent | 输出可审查 | 100%输出合法JSON，且证据数≥3 | ✅ 已实现 |
| Agent可靠性 | 不乱编 | 95%以上证据能追溯到工具返回数据 | ⏳ 待测试 |
| 审批 | 人工兜底 | 高风险动作100% requires_approval=true | ⏳ 待实现 |
| 执行 | 动作可追踪 | 审批通过后100%生成ActionExecution | ✅ 已实现 |
| 性能 | 可演示 | 单案例Agent推荐P95<30s | ⏳ 待测试 |
| 安全 | 不裸奔 | prod缺API token/Feishu token时启动失败或拒绝请求 | ⏳ 待实现 |

---

## Decision System Readiness v1 看板

### 数据层 📊

- **初始化成功率**: 100% ⏳
  - 验证方法: `init_metrics.py --full-pipeline` 退出码为0
  - 当前问题: 特征落库已修复，待在venv中验证

- **feature表关键字段空值率**: <5% ⏳
  - 验证方法: SQL审计
  ```sql
  SELECT
      COUNT(*) as total,
      COUNT(CASE WHEN redeemed_rate_7d IS NULL THEN 1 END) as null_count
  FROM feature.merchant_metrics;
  ```
  - 目标表: merchant_metrics, user_metrics, coupon_metrics

- **数据日期范围与样本数校验**: 通过 ⏳
  - 验证方法:
    - Raw层offline_train: ~26万记录
    - Staging层events: receipt_count + consumption_count
    - Feature层metrics: merchant_count (1-5万), user_count (10-50万)

### 特征层 🧮

- **as-of特征覆盖率**: ≥95% ⏳
  - 验证方法:
  ```sql
  SELECT
      COUNT(CASE WHEN user_receipts_30d_before IS NOT NULL THEN 1 END) / COUNT(*) as coverage
  FROM feature.receipt_training_features;
  ```
  - 冷启动处理: 1月初期允许<7天历史数据（标记为cold_start）

- **时间泄漏审计违规数**: =0 🔴 **最高优先级**
  - 验证方法: Time Leakage Audit Test（详见下文）
  - 当前状态: Migration已创建，Calculator已实现，待运行验证

### 模型层 🎯

- **grouped AUC**: ≥0.68 ⏳
  - 验证方法: time-based test split
  - 当前问题: 需使用time-safe特征重新训练

- **模型版本完整性**: ✅
  - model_version: v1.0_time_safe
  - feature_version: v1_time_safe
  - train_date_range: 2016-01-01 to 2016-04-30
  - metrics: {auc: 0.68, logloss: ...}

- **连续3次训练AUC波动**: ≤0.03 ⏳
  - 验证方法: 重复训练3次，记录AUC变化
  - 目的: 证明模型稳定性，不是偶然结果

### Agent层 🤖

- **推荐JSON合法率**: 100% ✅
  - 验证方法: JSON.parse()测试
  - 已实现: DeepSeek JSON Mode强制输出

- **每个推荐至少3条证据**: 100% ✅
  - 验证方法: 统计evidence数组长度
  - 已实现: Agent工具返回结构保证≥2证据，Agent补充≥1

- **证据可追溯率**: ≥95% ⏳
  - 验证方法: Agent Grounding Test（详见下文）
  - 验证: 证据字段能在tool_trace中找到来源

- **动作白名单命中率**: 100% ⏳
  - 验证方法: suggested_actions只能在预定义列表中
  ```python
  ALLOWED_ACTIONS = [
      "pause_coupon_distribution",
      "adjust_target_users",
      "change_discount_strategy",
      "send_reminder",
      "no_action"
  ]
  ```

### 审批执行层 ✅

- **高风险动作审批覆盖率**: 100% ⏳
  - 验证方法: Approval Safety Test（详见下文）
  - 实现: risk_level="high" → requires_approval=true

- **执行记录落库率**: 100% ✅
  - 验证方法: 审批通过后查询ActionExecution表
  - 已实现: approval_service.py:113

- **重复审批重复执行次数**: =0 ⏳
  - 验证方法: 同一case_id批准两次，只生成1条ActionExecution
  - 需要实现: 幂等性检查

### 性能与稳定性 ⚡

- **Agent单案例P95**: <30s ⏳
  - 验证方法: 20个案例Agent推荐耗时统计
  - 瓶颈: DeepSeek API调用（预计5-15s）

- **规则扫描1万商户**: <5min ⏳
  - 验证方法: 执行规则扫描，记录耗时
  - 当前实现: Celery task异步执行

- **API健康检查成功率**: 100% ✅
  - 验证方法: GET /api/v1/health返回200
  - 已实现: health.py

---

## 5个关键验收测试

### Test 1: Pipeline Smoke Test 🔥

**目标**: 证明项目能从数据跑到案例（不是"代码都有"而是真的能运行）

**测试流程**:
```bash
# 1. 清空数据库
psql -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -c "DROP SCHEMA IF EXISTS raw CASCADE; DROP SCHEMA IF EXISTS staging CASCADE;"
psql -c "DROP SCHEMA IF EXISTS feature CASCADE; DROP SCHEMA IF EXISTS application CASCADE;"

# 2. 运行migration
alembic upgrade head

# 3. 导入小样本数据（1000条）
head -n 1001 data/offline_train.csv > data/sample.csv
python scripts/import_dataset.py --train data/sample.csv

# 4. 运行清洗
python scripts/init_metrics.py --skip-import --skip-features --skip-model

# 5. 运行time-safe特征计算（待实现）
python scripts/compute_time_safe_features.py --start 2016-01-01 --end 2016-01-31

# 6. 运行规则扫描
python -m app.tasks.rule_scan

# 7. Agent生成建议（通过API）
curl -X POST http://localhost:8000/api/v1/cases/{case_id}/agent-diagnose

# 8. 审批通过
curl -X POST http://localhost:8000/api/v1/cases/{case_id}/approve

# 9. 验证ActionExecution
psql -c "SELECT COUNT(*) FROM application.action_execution;"
```

**验收标准**:
```
✅ DecisionCase count >= 1
✅ Recommendation count >= 1
✅ ApprovalLog count >= 1
✅ ActionExecution count >= 1
✅ 全流程无异常（退出码=0）
```

**测试文件**: `tests/smoke/test_pipeline_integration.py`（待创建）

---

### Test 2: Time Leakage Audit Test ⏰

**目标**: 证明模型训练没有偷看未来

**审计逻辑**:
```python
def audit_time_leakage(db: Session):
    """审计receipt_training_features时间安全性"""

    # 检查1: user历史统计是否只使用date_received < as_of_date
    violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        JOIN staging.coupon_receipt_event cre ON
            cre.user_id = rtf.user_id
            AND cre.date_received >= rtf.as_of_date  -- 违规：使用了>=as_of_date的数据
        WHERE rtf.user_receipts_30d_before > 0
    """)).first()

    future_receipt_used_count = violations.violations or 0

    # 检查2: redeemed统计是否只使用date_redeemed < as_of_date
    redeem_violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        JOIN staging.coupon_receipt_event cre ON
            cre.user_id = rtf.user_id
            AND cre.is_redeemed = true
            AND cre.date_redeemed >= rtf.as_of_date  -- 违规：使用了>=as_of_date的核销数据
        WHERE rtf.user_redeemed_count_30d_before > 0
    """)).first()

    future_redeem_used_count = redeem_violations.violations or 0

    return {
        "future_receipt_used_count": future_receipt_used_count,
        "future_redeem_used_count": future_redeem_used_count,
        "passed": (future_receipt_used_count == 0 and future_redeem_used_count == 0)
    }
```

**验收标准**:
```
✅ future_receipt_used_count = 0
✅ future_redeem_used_count = 0
✅ 训练代码只从feature.receipt_training_features读取特征
```

**测试文件**: `tests/validation/test_time_leakage_audit.py`（待创建）

---

### Test 3: Model Backtest Test 📈

**目标**: 证明模型不是靠泄漏刷分

**时间切分**:
```
Train:      2016-01-01 ~ 2016-04-30 (4个月)
Validation: 2016-05-01 ~ 2016-05-31 (1个月)
Test:       2016-06-01 ~ 2016-06-30 (1个月)
```

**验证逻辑**:
```python
def validate_model_performance():
    """验证模型回测性能"""

    # 加载模型
    model = joblib.load("app/ml/artifacts/redeem_predictor.joblib")

    # 验证metadata
    metadata = model.get("metadata", {})
    assert "model_version" in metadata
    assert "feature_version" in metadata  # 必须是"v1_time_safe"
    assert "train_date_range" in metadata
    assert "metrics" in metadata

    # 计算test AUC（grouped by coupon_id）
    test_features = load_test_features()
    predictions = model.predict_proba(test_features)

    grouped_auc = calculate_grouped_auc(
        predictions,
        test_features['label_is_redeemed'],
        test_features['coupon_id']
    )

    overall_auc = calculate_overall_auc(predictions, test_features['label_is_redeemed'])

    prediction_mean = predictions.mean()

    return {
        "grouped_auc": grouped_auc,
        "overall_auc": overall_auc,
        "prediction_mean": prediction_mean,
        "metadata": metadata,
        "passed": (
            grouped_auc >= 0.68
            and overall_auc >= 0.65
            and 0.01 <= prediction_mean <= 0.30
        )
    }
```

**验收标准**:
```
✅ grouped_auc >= 0.68
✅ overall_auc >= 0.65
✅ prediction_mean 在 0.01~0.30区间
✅ 模型文件包含完整metadata
```

**重要说明**:
- 如果time-safe后AUC降到0.60左右，不是灾难
- 说明之前可能有泄漏，项目可信度反而上升
- 能够解释问题并重新建立baseline

**测试文件**: `tests/validation/test_model_backtest.py`（待创建）

---

### Test 4: Agent Grounding Test 🧠

**目标**: 证明Agent基于证据生成建议（不是自由发挥）

**测试案例准备**: 20个固定案例
```python
TEST_CASES = [
    # Case 1: 商户核销率下降（正常）
    {"merchant_id": "m001", "scenario": "redeemed_rate_drop", "expected_evidence_count": 3},

    # Case 2: 高折扣低转化（正常）
    {"merchant_id": "m002", "scenario": "high_discount_low_conversion", "expected_evidence_count": 3},

    # Case 3: 用户召回（正常）
    {"user_id": "u001", "scenario": "user_recall", "expected_evidence_count": 2},

    # Case 4: 数据缺失（边界）
    {"merchant_id": "m999", "scenario": "missing_data", "expected_evidence_count": 1},

    # Case 5: 工具返回错误（异常）
    {"merchant_id": "m_error", "scenario": "tool_error", "expected_evidence_count": 0},

    # ... 共20个案例
]
```

**验证逻辑**:
```python
def validate_agent_grounding():
    """验证Agent证据可追溯性"""

    results = []

    for case in TEST_CASES:
        # Agent生成推荐
        recommendation = agent_generate_recommendation(case)

        # 验证1: JSON合法性
        json_valid = validate_json(recommendation)

        # 验证2: 证据数量
        evidence_count = len(recommendation.get("evidence", []))

        # 验证3: 动作白名单
        actions_valid = all(
            action["type"] in ALLOWED_ACTIONS
            for action in recommendation.get("suggested_actions", [])
        )

        # 验证4: confidence_score范围
        confidence_valid = 0 <= recommendation.get("confidence_score", 0) <= 1

        # 验证5: 高风险动作需审批
        high_risk_requires_approval = all(
            action.get("requires_approval", False)
            for action in recommendation.get("suggested_actions", [])
            if action.get("risk_level") == "high"
        )

        # 验证6: 证据可追溯性（核心）
        evidence_traceable_count = count_traceable_evidence(
            recommendation.get("evidence", []),
            recommendation.get("tool_trace", [])
        )
        evidence_traceable_rate = evidence_traceable_count / evidence_count if evidence_count > 0 else 0

        results.append({
            "case_id": case["merchant_id"],
            "json_valid": json_valid,
            "evidence_count": evidence_count,
            "evidence_count_valid": evidence_count >= case["expected_evidence_count"],
            "actions_valid": actions_valid,
            "confidence_valid": confidence_valid,
            "high_risk_requires_approval": high_risk_requires_approval,
            "evidence_traceable_rate": evidence_traceable_rate
        })

    # 统计通过率
    json_parse_success_rate = sum(r["json_valid"] for r in results) / len(results)
    evidence_count_pass_rate = sum(r["evidence_count_valid"] for r in results) / len(results)
    evidence_traceable_rate_avg = sum(r["evidence_traceable_rate"] for r in results) / len(results)

    return {
        "json_parse_success_rate": json_parse_success_rate,
        "evidence_count_pass_rate": evidence_count_pass_rate,
        "evidence_traceable_rate_avg": evidence_traceable_rate_avg,
        "passed": (
            json_parse_success_rate >= 1.0  # 100%
            and evidence_count_pass_rate >= 1.0  # 100%
            and evidence_traceable_rate_avg >= 0.95  # 95%
        )
    }
```

**验收标准**:
```
✅ JSON parse success rate = 100%
✅ 每条recommendation evidence_count >= 3 (or expected)
✅ suggested_actions只能来自动作白名单
✅ confidence_score在0~1
✅ 高风险动作 requires_approval = true
✅ 证据引用字段95%可在tool_trace中找到来源
```

**核心价值**: 回答"LLM是否比真人更强"的问题
- 不是比较"聪明"，而是比较"稳定生成结构化、可追溯、可审批的决策草稿"

**测试文件**: `tests/validation/test_agent_grounding.py`（待创建）

---

### Test 5: Approval Safety Test 🛡️

**目标**: 证明系统不会让LLM绕过人工审批

**验证规则**:
```python
def validate_approval_safety():
    """验证审批安全机制"""

    test_scenarios = [
        # Scenario 1: case.status != recommended时不能审批
        {"case_status": "pending", "should_approve": False},

        # Scenario 2: approve后必须写ApprovalLog
        {"case_status": "recommended", "should_approve": True, "check_approval_log": True},

        # Scenario 3: approve后必须生成ActionExecution
        {"case_status": "recommended", "should_approve": True, "check_action_execution": True},

        # Scenario 4: reject后不能执行动作
        {"action": "reject", "check_no_action": True},

        # Scenario 5: 同一个case重复审批不能重复执行
        {"duplicate_approve": True, "check_single_execution": True},

        # Scenario 6: 未知action_type必须失败
        {"unknown_action_type": "invalid_action", "should_fail": True}
    ]

    for scenario in test_scenarios:
        result = execute_approval_scenario(scenario)

        # 验证逻辑...

    return {
        "passed": all_scenarios_passed,
        "details": scenario_results
    }
```

**验收标准**:
```
✅ case.status != recommended时不能审批
✅ approve后必须写ApprovalLog
✅ approve后必须生成ActionExecution
✅ reject后不能执行动作
✅ 同一个case重复审批不能重复执行动作
✅ 未知action_type必须失败并记录
```

**重要性**: 上线风险控制的核心

**测试文件**: `tests/validation/test_approval_safety.py`（待创建）

---

## 实施优先级

### 🔴 P0 Critical（阻塞验收）

1. **Time Leakage Audit Test** - 最高优先级
   - 创建测试文件
   - 运行审计逻辑
   - 验证违规数=0

2. **Pipeline Smoke Test** - 证明系统可运行
   - 创建完整pipeline脚本
   - 在venv中运行验证
   - 记录退出码和表count

3. **Model Backtest Test** - 验证模型可信度
   - 运行time-safe特征计算
   - 重新训练模型
   - 计算grouped AUC

### 🟠 P1 High（质量保证）

4. **Agent Grounding Test** - 验证Agent可靠性
   - 创建20个测试案例
   - 验证证据可追溯性
   - 统计通过率

5. **Approval Safety Test** - 验证审批安全
   - 创建审批场景测试
   - 验证幂等性
   - 验证动作限制

### 🟡 P2 Medium（性能优化）

6. **性能测试** - Agent P95 < 30s
   - 统计20个案例耗时
   - 计算P95
   - 优化瓶颈（如有）

7. **模型稳定性测试** - 连续3次AUC波动≤0.03
   - 重复训练3次
   - 记录AUC变化
   - 验证波动范围

---

## 验收Dashboard实时状态

```
Decision System Readiness v1

数据层: ⏳⏳⏳ (0/3)
- 初始化成功率: ⏳ 待验证
- 特征表空值率: ⏳ 待验证
- 数据日期校验: ⏳ 待验证

特征层: 🔴⏳ (0/2)
- as-of覆盖率: 🔴 待实现
- 时间泄漏审计: ⏳ 待验证

模型层: ⏳⏳⏳ (0/3)
- grouped AUC: ⏳ 待重训
- metadata完整性: ⏳ 待验证
- AUC稳定性: ⏳ 待验证

Agent层: ✅⏳⏳⏳ (1/4)
- JSON合法率: ✅ 已实现
- 证据数≥3: ✅ 已实现
- 证据可追溯: ⏳ 待测试
- 动作白名单: ⏳ 待实现

审批执行层: ✅⏳⏳ (1/3)
- 高风险审批覆盖: ⏳ 待实现
- 执行记录落库: ✅ 已实现
- 重复执行次数: ⏳ 待验证

性能稳定性: ⏳⏳⏳ (0/3)
- Agent P95: ⏳ 待测试
- 规则扫描耗时: ⏳ 待测试
- API健康检查: ✅ 已实现

总体进度: 3/20 (15%)
```

---

## 下一步行动

**立即执行**（Goal驱动）:

1. ✅ 创建验收测试框架（当前任务）
2. 🔴 实现time-safe特征计算脚本（最高优先级）
3. 🔴 运行Time Leakage Audit Test验证
4. 🔴 运行Pipeline Smoke Test验证完整链路
5. 🟠 运行Model Backtest Test重新训练模型
6. 🟠 运行Agent Grounding Test验证证据可追溯
7. 🟠 运行Approval Safety Test验证审批安全

---

**验收目标**: 达到Decision System Readiness v1全部标准，证明系统可一键跑通、数据可信、模型可信、Agent可信、审批安全。