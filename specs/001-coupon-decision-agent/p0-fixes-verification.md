# P0 Fixes Verification Report

**Date**: 2026-05-18
**Status**: P0-1, P0-2, P0-3 COMPLETED, P0-4 ADDED (smoke tests)

## Summary

修复了审查中识别的最关键 P0 问题：
1. ✅ init_metrics.py 特征落库问题
2. ✅ Agent 工具契约不一致（KeyError）
3. ✅ 添加缺失的 Agent 工具
4. ✅ 创建 smoke tests 防止再次失效

## P0-1: init_metrics.py 特征落库

### 问题诊断
- **位置**: `scripts/init_metrics.py:95-127`
- **症状**: 特征只计算不保存，运行后 feature 表无数据
- **根因**: `calculate_merchant_metrics()` 只返回 list，未调用 `save_merchant_metrics()`

### 修复方案
```python
# 修复前
merchant_metrics = merchant_calc.calculate_merchant_metrics()
logger.info(f"✓ Merchant metrics: {len(merchant_metrics)} merchants")

# 修复后
merchant_result = merchant_calc.save_merchant_metrics()
logger.info(f"✓ Merchant metrics: {merchant_result.get('merchants_processed', 0)} merchants")

# User metrics - bulk save
user_metrics = calculate_user_metrics(db)
db.execute(text("TRUNCATE TABLE feature.user_metrics"))
db.bulk_save_objects(user_metrics)

# Coupon metrics
coupon_result = coupon_calc.save_coupon_metrics()
```

### 验证清单
- [ ] 运行 `python scripts/init_metrics.py --skip-import --skip-clean --skip-model`
- [ ] 检查 `feature.merchant_metrics` 表有数据
- [ ] 检查 `feature.user_metrics` 表有数据
- [ ] 检查 `feature.coupon_metrics` 表有数据

### 已修复附加问题
- **subprocess 调用**: `"python"` → `sys.executable`（适配 venv 环境）

## P0-2: Agent 工具契约不一致

### 问题诊断
- **位置**: `app/agents/prompts/decision_prompt.py:169-172`
- **症状**: 商户案例构建 prompt 时抛 KeyError 'discount_type'
- **根因**: `coupon_conversion_tool` 返回嵌套结构 `{coupon_id, conversion_metrics: {...}}`
         但 `decision_prompt` 直接访问 `c['discount_type']`

### 修复方案
```python
# 修复前（会导致 KeyError）
for c in coupon_data.get("coupons", [])[:5]:
    f"{c['coupon_id']}: {c['discount_type']}, "
    f"核销率 {c['redeemed_rate']:.2%}"

# 修复后（正确访问嵌套结构）
for c in coupon_data.get("coupons", [])[:5]:
    metrics = c.get('conversion_metrics', {})
    f"{c['coupon_id']}: {metrics.get('discount_type', '未知')}, "
    f"核销率 {metrics.get('redeemed_rate', 0):.2%}"
```

### 验证清单
- [ ] 用真实工具输出测试 `_format_tool_results()`
- [ ] 商户案例 prompt 格式化不抛异常
- [ ] 案例详情正确显示证据和风险级别

## P0-3: 缺失的 Agent 工具

### 问题诊断
- **缺失工具**: `get_user_metrics`, `get_recent_receipts`
- **影响**: Agent 无法查询用户指标和近期领券记录，决策证据不足

### 修复方案
新增两个工具：
1. **get_user_metrics**: 查询用户 engagement metrics（领券数、核销率、距离偏好）
2. **get_recent_receipts**: 查询近期领券事件（按商户/用户筛选，最近7天）

### 工具注册
```python
AVAILABLE_TOOLS = {
    "get_merchant_metrics": {...},
    "get_coupon_conversion": {...},
    "get_user_metrics": {      # NEW
        "function": get_user_metrics,
        "parameters": {"user_id": "User ID to query (required)"},
    },
    "get_recent_receipts": {   # NEW
        "function": get_recent_receipts,
        "parameters": {
            "merchant_id": "Merchant ID (optional)",
            "user_id": "User ID (optional)",
            "days": "Recent days (default: 7)",
        },
    },
}
```

### 验证清单
- [ ] `get_user_metrics(db, user_id="test")` 返回有效结果
- [ ] `get_recent_receipts(db, merchant_id="test", days=7)` 返回有效结果
- [ ] Agent 决策服务可以调用这些工具

## P0-4: Smoke Tests

### 目的
防止 README 指令再次失效，建立最基本的可用性检查。

### 测试内容
- Python version ≥ 3.12
- Critical dependencies installed
- Project structure完整性
- .env 文件存在
- Config loading正常
- init_metrics subprocess调用正确性
- Agent tools registry完整性
- Agent prompt formatting不崩溃
- FastAPI app startup正常

### 运行方式
```bash
# 在虚拟环境中运行
source venv/bin/activate
python tests/smoke/test_basic_sanity.py
```

### 验证清单
- [ ] 在 venv 中运行 smoke tests 全部通过
- [ ] 添加到 CI pipeline（后续）

## 下一步（P0 继续）

### P0-3: 时间泄漏修复
- 创建 `feature.receipt_training_features` 表
- 实现 as-of 特征计算（只使用 `date_received < 当前样本date_received`）
- 重新训练模型，重新声明 AUC

### P0-4: ML 接入 Agent
- 创建 `prediction.receipt_prediction` 表
- 实现 `get_redeem_prediction_summary` 工具
- Agent 返回高层摘要（高潜用户占比、预计核销增量等）

## 提交记录

```
2a5324c fix(P0): resolve critical pipeline and agent contract issues
```

## 文件变更

- `scripts/init_metrics.py`: 特征落库修复
- `app/agents/prompts/decision_prompt.py`: 契约不一致修复
- `app/agents/tools/user_metrics_tool.py`: 新增工具
- `app/agents/tools/recent_receipts_tool.py`: 新增工具
- `app/agents/tools/__init__.py`: 工具注册
- `tests/smoke/test_basic_sanity.py`: 新增 smoke tests

---

**状态**: P0 修复已完成 1/4，等待验证和继续修复时间泄漏。