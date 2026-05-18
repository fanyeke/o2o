# M1验收测试执行脚本

**验收目标**: FeatureExtractor只读receipt_training_features，0时间泄漏

---

## 前置条件检查

```bash
# 1. 检查特征计算完成度
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT
    COUNT(*) as total,
    MIN(as_of_date) as min_date,
    MAX(as_of_date) as max_date,
    COUNT(*) / 1011990.0 * 100 as progress_pct
FROM feature.receipt_training_features
"
```

验收标准：
- total >= 1,000,000 (允许±1%误差)
- min_date = '2016-01-01'
- max_date = '2016-06-15'
- progress_pct >= 99%

---

## M1验收测试（最高优先级）

### test_time_leakage_audit.py - 10个审计测试

```bash
PYTHONPATH=/home/zzz/project/o2o venv/bin/python -m pytest tests/validation/test_time_leakage_audit.py -v
```

预期输出：
```
tests/validation/test_time_leakage_audit.py::test_user_receipts_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_user_redeemed_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_merchant_receipts_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_merchant_redeemed_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_coupon_receipts_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_coupon_redeemed_time_leakage PASSED
tests/validation/test_time_leakage_audit.py::test_no_current_receipt_in_features PASSED
tests/validation/test_time_leakage_audit.py::test_feature_extractor_uses_time_safe_table PASSED ✓ 代码审计
tests/validation/test_time_leakage_audit.py::test_feature_coverage PASSED ✓ 覆盖率>=95%
tests/validation/test_time_leakage_audit.py::test_feature_version_correct PASSED ✓ v1_time_safe

========================= 10 passed in XXs =========================
```

验收标准：
- ✅ 10个测试全部passed
- ✅ violations count = 0（所有SQL审计）
- ✅ coverage >= 95%
- ✅ feature_version = 'v1_time_safe'
- ✅ FeatureExtractor代码审计通过

---

## 特征覆盖率验证

```bash
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE user_receipts_30d_before IS NOT NULL) as user_covered,
    COUNT(*) FILTER (WHERE merchant_receipts_30d_before IS NOT NULL) as merchant_covered,
    COUNT(*) FILTER (WHERE coupon_total_receipts_before IS NOT NULL) as coupon_covered,
    ROUND(COUNT(*) FILTER (WHERE user_receipts_30d_before IS NOT NULL) / COUNT(*)::float * 100, 2) as user_coverage_pct,
    ROUND(COUNT(*) FILTER (WHERE merchant_receipts_30d_before IS NOT NULL) / COUNT(*)::float * 100, 2) as merchant_coverage_pct,
    ROUND(COUNT(*) FILTER (WHERE coupon_total_receipts_before IS NOT NULL) / COUNT(*)::float * 100, 2) as coupon_coverage_pct
FROM feature.receipt_training_features
"
```

验收标准：
- ✅ user_coverage >= 95%
- ✅ merchant_coverage >= 95%
- ✅ coupon_coverage >= 95%

---

## 时间泄漏违规检查

```bash
# User violations
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT COUNT(*) as violations
FROM feature.receipt_training_features rtf
JOIN staging.coupon_receipt_event cre ON
    cre.user_id = rtf.user_id
    AND cre.date_received >= rtf.as_of_date
WHERE rtf.user_receipts_30d_before > 0
"

# Merchant violations
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT COUNT(*) as violations
FROM feature.receipt_training_features rtf
JOIN staging.coupon_receipt_event cre ON
    cre.merchant_id = rtf.merchant_id
    AND cre.date_received >= rtf.as_of_date
WHERE rtf.merchant_receipts_7d_before > 0
   OR rtf.merchant_receipts_30d_before > 0
"

# Coupon violations
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
SELECT COUNT(*) as violations
FROM feature.receipt_training_features rtf
JOIN staging.coupon_receipt_event cre ON
    cre.coupon_id = rtf.coupon_id
    AND cre.date_received >= rtf.as_of_date
WHERE rtf.coupon_total_receipts_before > 0
"
```

验收标准：
- ✅ 所有violations = 0

---

## M1验收总结命令

一键验证脚本：

```bash
# M1验收完整验证
echo "=== M1验收：时间安全特征真正接入训练 ==="

# 1. 特征计算完成度
echo "1. 检查特征计算完成度..."
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -t -c "
SELECT COUNT(*) || ' receipts (' || ROUND(COUNT(*) / 1011990.0 * 100, 2) || '%)'
FROM feature.receipt_training_features
"

# 2. 运行时间泄漏审计测试
echo "2. 运行时间泄漏审计测试..."
PYTHONPATH=/home/zzz/project/o2o venv/bin/python -m pytest tests/validation/test_time_leakage_audit.py -v --tb=short

# 3. 检查覆盖率
echo "3. 检查特征覆盖率..."
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -t -c "
SELECT
    'User: ' || ROUND(COUNT(*) FILTER (WHERE user_receipts_30d_before IS NOT NULL) / COUNT(*)::float * 100, 1) || '%, '
    || 'Merchant: ' || ROUND(COUNT(*) FILTER (WHERE merchant_receipts_30d_before IS NOT NULL) / COUNT(*)::float * 100, 1) || '%, '
    || 'Coupon: ' || ROUND(COUNT(*) FILTER (WHERE coupon_total_receipts_before IS NOT NULL) / COUNT(*)::float * 100, 1) || '%'
FROM feature.receipt_training_features
"

echo "=== M1验收完成 ==="
```

---

## M1验收目标达成条件

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| FeatureExtractor使用receipt_training_features | 100% | test_feature_extractor_uses_time_safe_table |
| 直接join旧特征表 | 0处 | 代码审计 + grep验证 |
| test_time_leakage_audit.py | 10/10通过 | pytest运行 |
| 特征版本 | v1_time_safe | test_feature_version_correct |
| 特征覆盖率 | >= 95% | test_feature_coverage + SQL验证 |
| 泄漏审计违规数 | 0 | SQL审计查询 |

**验收成功**: 所有6项指标达标

---

## 当前进度

**Time-safe特征计算**: 361,500/1,011,990 (35.72%)
**预计完成时间**: ~15:03（约2小时）
**验收准备**: ✅ 完整（测试+验证脚本+验收标准）

**下一步**: 特征计算完成后立即执行M1验收命令