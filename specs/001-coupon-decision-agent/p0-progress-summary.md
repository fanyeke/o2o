# P0 修复进度总结

**时间**: 2026-05-18
**当前状态**: P0-1, P0-2 完成，已推送到 GitHub

## 已完成 ✅

### 1. init_metrics.py 特征落库修复
**文件**: `scripts/init_metrics.py`

**变更**:
- Line 106: 使用 `save_merchant_metrics()` 替代仅计算
- Line 111-117: User/Coupon metrics 正确落库
- Line 58, 138: subprocess 使用 `sys.executable`

**验证命令**（需在 venv 中运行）:
```bash
source venv/bin/activate
python scripts/init_metrics.py --skip-import --skip-clean --skip-model

# 验证数据库
psql -U coupon_user -d coupon_agent -c "SELECT COUNT(*) FROM feature.merchant_metrics;"
psql -U coupon_user -d coupon_agent -c "SELECT COUNT(*) FROM feature.user_metrics;"
psql -U coupon_user -d coupon_agent -c "SELECT COUNT(*) FROM feature.coupon_metrics;"
```

### 2. Agent 工具契约修复
**文件**: `app/agents/prompts/decision_prompt.py`

**变更**:
- Line 169-172: 正确访问嵌套的 `conversion_metrics`
- 使用 `.get()` 防止 KeyError

**影响**: 商户案例 prompt 格式化不再崩溃

### 3. 缺失工具补充
**新增文件**:
- `app/agents/tools/user_metrics_tool.py`
- `app/agents/tools/recent_receipts_tool.py`

**注册**: `app/agents/tools/__init__.py`

**工具列表**:
- get_merchant_metrics ✅
- get_coupon_conversion ✅
- get_user_metrics ✅ (NEW)
- get_recent_receipts ✅ (NEW)

### 4. Smoke Tests
**新增文件**: `tests/smoke/test_basic_sanity.py`

**覆盖**:
- Python version, dependencies
- Project structure, config loading
- Agent tools registry, prompt formatting
- FastAPI startup

**运行命令**（需在 venv 中运行）:
```bash
source venv/bin/activate
python tests/smoke/test_basic_sanity.py
```

## 下一步（P0 继续） 🔄

### P0-3: 时间泄漏修复 ⏳

**问题诊断**:
- 当前 ML 训练特征直接 join 全局快照，使用了未来数据
- 用户/商户/券指标用最新日期聚合，包含样本日期之后的核销结果

**解决方案**:
1. 创建新表 `feature.receipt_training_features`
2. 实现 as-of 特征计算逻辑：
   ```python
   # 关键约束
   WHERE date_received < current_sample.date_received

   # 核销类分子还要限制
   WHERE date_redeemed < current_sample.date_received
   ```
3. 重新训练模型，重新声明 AUC

**预期工作量**: 2-3 小时

**文件**:
- 新增 migration: `alembic/versions/xxx_receipt_training_features.py`
- 修改: `app/ml/train/feature_extractor.py`
- 新增: `app/domain/feature/receipt_training_features.py`

### P0-4: ML 接入 Agent ⏳

**问题**: Agent 未使用 ML 预测结果，仅依赖规则和指标

**解决方案**:
1. 创建预测表 `prediction.receipt_prediction`
2. 实现 `get_redeem_prediction_summary` 工具
3. Agent 工具返回高层摘要：
   - 高潜用户占比
   - 平均核销概率
   - 低效券数量
   - 预计核销增量
   - 预计补贴成本

**预期工作量**: 1-2 小时

**文件**:
- 新增 migration: `alembic/versions/xxx_receipt_prediction.py`
- 新增: `app/domain/prediction/receipt_prediction.py`
- 新增: `app/agents/tools/prediction_summary_tool.py`
- 修改: `app/agents/tools/__init__.py`

## Git 提交记录

```
8fe5f02 fix: resolve P0 UX blockers for API validation
2a5324c fix(P0): resolve critical pipeline and agent contract issues
2d2a804 docs: add P0 fixes verification report
```

**已推送到**: https://github.com/fanyeke/o2o.git (main branch)

## 验证清单

### 立即验证（在 venv 中）
- [ ] Smoke tests 全部通过
- [ ] init_metrics.py 运行成功，特征表有数据
- [ ] Agent prompt 格式化不崩溃

### 后续验证（P0-3 完成后）
- [ ] receipt_training_features 表有数据
- [ ] 模型重新训练，AUC 基于无泄漏数据
- [ ] 特征全部使用历史数据（< sample date）

### 最终验证（P0-4 完成后）
- [ ] prediction 表有数据
- [ ] Agent 工具返回预测摘要
- [ ] Agent 决策包含 ML 模型结果

## 当前阻塞

**无法运行验证**: 系统当前不在虚拟环境中，依赖未安装

**建议操作**:
1. 在 venv 中运行 smoke tests 验证基础修复
2. 确认 init_metrics.py 能正常落库
3. 继续修复 P0-3 时间泄漏问题

---

**结论**: P0 前两项修复已完成，等待验证后继续修复时间泄漏和 ML 接入。