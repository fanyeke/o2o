# 验收测试执行计划

**Status**: Time-safe特征计算进行中（15.4%）
**Expected completion**: ~14:30 (2.4小时剩余)
**Validation tests**: 等待特征计算完成后10分钟内执行

---

## ✅ 前置条件验证（已完成）

### 测试文件准备
```
tests/validation/test_time_leakage_audit.py  ✓ (10个审计测试)
tests/validation/test_model_backtest.py      ✓ (模型验证)
tests/validation/test_agent_grounding.py     ✓ (Agent证据可追溯)
tests/validation/test_approval_safety.py     ✓ (审批安全)
tests/smoke/test_pipeline_integration.py     ✓ (完整链路)
tests/smoke/test_basic_sanity.py             ✓ (基础验证)
```

### 测试依赖验证
```
pytest ✓
joblib ✓
sqlalchemy ✓
```

### 数据层准备
```
数据库连接        ✓ (Docker PostgreSQL port 5433)
Migration运行     ✓ (alembic upgrade head)
数据导入清洗      ✓ (1,011,990 receipt events)
数据重复清理      ✓ (41,292 duplicates removed)
基础特征计算      ✓ (merchants/users/coupons)
Time-safe特征计算 🔄 进行中（155,000/1,011,990）
```

---

## 🎯 验收标准（Decision System Readiness v1）

### 量化指标（11项）

| 模块 | 验收标准 | 当前状态 | 进度 |
|------|---------|---------|------|
| 初始化 | 从零可复现 | 待验证 | 0% |
| 数据质量 | 特征表空值率<5% | 🔄 计算中 | 15% |
| 时间泄漏 | 违规数=0 | 待验证 | 0% |
| 模型效果 | grouped AUC≥0.68 | 待训练验证 | 0% |
| 模型稳定性 | AUC方差≤0.03 | 待验证 | 0% |
| Agent输出 | JSON合法100% | 待验证 | 0% |
| Agent可靠性 | 证据可追溯≥95% | 待验证 | 0% |
| 审批覆盖 | 6场景全通过 | 待验证 | 0% |
| 执行追踪 | 全链路可追踪 | 待验证 | 0% |
| 性能 | 可演示<10s | 待验证 | 0% |
| 安全 | 不裸奔 | 待验证 | 0% |

**平均进度**: 15% (特征计算进行中)

---

## 📋 验收测试执行顺序（完成后）

### 等待条件检查

```bash
# 1. 检查特征计算完成
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT
    COUNT(*) as total,
    MIN(as_of_date) as min_date,
    MAX(as_of_date) as max_date,
    COUNT(*) / 1011990.0 * 100 as progress_pct
FROM feature.receipt_training_features
"

验收标准:
- total ≈ 1,011,990 (允许±1%误差)
- min_date = 2016-01-01
- max_date = 2016-06-15
- progress_pct ≥ 99%
```

### 测试执行序列

```bash
# 2. Time Leakage Audit Test (预计2分钟)
PYTHONPATH=/home/zzz/project/o2o venv/bin/pytest tests/validation/test_time_leakage_audit.py -v

验收标准:
- 10个测试全部passed
- violations count = 0
- feature_coverage ≥ 95%
- feature_version = 'v1_time_safe'

预期输出:
✓ test_user_receipts_time_leakage PASSED
✓ test_user_redeemed_time_leakage PASSED
✓ test_merchant_receipts_time_leakage PASSED
✓ test_merchant_redeemed_rate_time_leakage PASSED
✓ test_redeemed_flag_time_leakage PASSED
✓ test_feature_coverage PASSED
✓ test_feature_extractor_uses_time_safe_table PASSED
✓ test_feature_version_correct PASSED
✓ test_as_of_date_range_complete PASSED
✓ test_time_safe_feature_calculator_logic PASSED
```

```bash
# 3. Pipeline Smoke Test (预计3分钟)
PYTHONPATH=/home/zzz/project/o2o venv/bin/pytest tests/smoke/test_pipeline_integration.py -v -s

验收标准:
- 11个测试全部passed
- DecisionCase count ≥ 1
- Recommendation count ≥ 1
- ApprovalLog count ≥ 1
- ActionExecution count ≥ 1

预期输出:
✓ test_step_1_clear_database PASSED
✓ test_step_2_run_migrations PASSED
✓ test_step_3_import_sample_data PASSED
✓ test_step_4_clean_data PASSED
✓ test_step_5_compute_features PASSED
✓ test_step_6_rule_scan PASSED
✓ test_step_7_generate_decision_case PASSED
✓ test_step_8_generate_recommendation PASSED
✓ test_step_9_approve_case PASSED
✓ test_step_10_generate_action_execution PASSED
✓ test_final_counts PASSED
```

```bash
# 4. Model Backtest Test (预计1分钟)
PYTHONPATH=/home/zzz/project/o2o venv/bin/pytest tests/validation/test_model_backtest.py -v

验收标准:
- model_metadata_complete passed
- feature_version = 'v1_time_safe'
- grouped_auc ≥ 0.68
- prediction_mean in [0.01, 0.30]

预期输出:
✓ test_model_metadata_complete PASSED
✓ test_model_performance_realistic PASSED
✓ test_feature_coverage_in_training PASSED
```

```bash
# 5. Agent Grounding Test (预计1分钟)
PYTHONPATH=/home/zzz/project/o2o venv/bin/pytest tests/validation/test_agent_grounding.py -v

验收标准:
- 20个测试全部passed
- JSON parse success rate = 100%
- evidence_count ≥ 3 per recommendation
- evidence_traceable_rate ≥ 95%
- actions_whitelist_hit_rate = 100%

预期输出:
✓ test_agent_grounding[param0] PASSED
✓ test_agent_grounding[param1] PASSED
...
✓ test_all_scenarios_covered PASSED
✓ test_action_whitelist_complete PASSED
✓ test_json_parse_success_rate PASSED
```

```bash
# 6. Approval Safety Test (预计1分钟)
PYTHONPATH=/home/zzz/project/o2o venv/bin/pytest tests/validation/test_approval_safety.py -v

验收标准:
- 6个场景全部passed
- 幂等性验证通过
- 状态机转换正确

预期输出:
✓ test_cannot_approve_pending_case PASSED
✓ test_approve_creates_approval_log PASSED
✓ test_approve_creates_action_execution PASSED
✓ test_reject_does_not_execute PASSED
✓ test_duplicate_approval_idempotent PASSED
✓ test_unknown_action_fails_gracefully PASSED
```

---

## ⏱️ 时间估算

**特征计算剩余时间**: ~2.4小时（141天待处理）
**验收测试总时间**: ~10分钟
**总计**: ~2.5小时达到验收目标

---

## 📊 验收Dashboard目标状态

```
验收准备工作: ██████████ 100% ✓
验收执行验证: ██████████ 100% ✓

数据层:
- 数据库连接 ✓
- Migration ✓
- 数据导入清洗 ✓
- 数据重复清理 ✓
- Time-safe特征计算 ✓
- 特征覆盖率验证 ✓

验收测试:
- Time Leakage Audit ✓ 10/10
- Pipeline Smoke ✓ 11/11
- Model Backtest ✓ 3/3
- Agent Grounding ✓ 20/20
- Approval Safety ✓ 6/6

量化指标:
- 初始化成功率 100% ✓
- 数据质量 <5%空值率 ✓
- 时间泄漏 0违规 ✓
- 模型效果 ≥0.68 AUC ✓
- Agent可靠性 ≥95%可追溯 ✓
- 审批安全 6场景全通过 ✓

总体进度: ██████████ 100% ✓
```

---

## 🎯 完成标志

**Decision System Readiness v1达成条件**:

1. ✅ receipt_training_features count ≈ 1,011,990
2. ✅ as_of_date范围完整（2016-01-01 to 2016-06-15）
3. ✅ Time Leakage Audit全部通过（违规数=0）
4. ✅ Pipeline Smoke Test全部通过（完整链路无异常）
5. ✅ Model Backtest验证通过（grouped AUC ≥ 0.68）
6. ✅ Agent Grounding验证通过（证据可追溯≥95%）
7. ✅ Approval Safety验证通过（6场景全通过）

**验收成功**: 11项量化指标全部达标

---

## 📝 Git提交准备

**验收完成后提交**:

```bash
git add specs/001-coupon-decision-agent/ tests/validation/
git commit -m "feat: complete Decision System Readiness v1 validation

- Time-safe features computed (1,011,990 receipts)
- Time leakage audit passed (0 violations)
- Pipeline smoke test passed (11/11)
- Model backtest validated (AUC ≥ 0.68)
- Agent grounding verified (95%+ traceable)
- Approval safety tested (6/6 scenarios)

All 11 acceptance criteria achieved."

git push origin main
```

---

## 💡 监控命令

```bash
# 实时进度监控
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT COUNT(*) as receipts,
       COUNT(*) / 1011990.0 * 100 as progress_pct,
       MAX(as_of_date) as current_date,
       '2016-06-15'::date - MAX(as_of_date) as days_remaining
FROM feature.receipt_training_features
"

# 后台监控任务
cat /tmp/claude-1000/-home-zzz-project-o2o/9413cce5-fddc-4cb9-b4f3-6e55ead68f3e/tasks/bpb8srixq.output

# 计算进程状态
ps aux | grep compute_time_safe_features | grep -v grep

# 计算日志
tail -100 /tmp/time_safe_final.log
```

---

## 🎯 当前状态总结

**进度**: 特征计算15.4%进行中
**预计**: ~14:30完成特征计算，~14:40完成所有验收
**距离Decision System Readiness v1**: 约2.5小时

**任务持续完成**: 所有准备工作已就绪，等待特征计算完成后立即执行验收流程。