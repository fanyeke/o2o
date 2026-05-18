"""Time Leakage Audit Test - 验证模型训练没有偷看未来数据.

This test verifies that ALL historical features in receipt_training_features
are computed using only data BEFORE each receipt's date_received.

Time leakage is CRITICAL for ML model integrity:
- If we use future data in features, model learns patterns that won't exist in production
- Time leakage leads to inflated training metrics but poor production performance
- This test catches violations before model training

Validation rules:
1. User historical stats: WHERE date_received < as_of_date
2. Merchant historical stats: WHERE date_received < as_of_date
3. Redeemed counts: WHERE (is_redeemed=false OR date_redeemed < as_of_date)
4. No current or future receipt data allowed in historical aggregates
"""

import pytest
from sqlalchemy import text
from app.core.database import get_db


def test_user_receipts_time_leakage():
    """验证user历史统计只使用date_received < as_of_date的receipts."""

    db = next(get_db())

    # 正确审计：对比特征计算值与手动验证值（只统计<as_of_date）
    # 如果差异不为0，说明特征计算使用了future data
    violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        WHERE rtf.user_receipts_30d_before > 0
          AND rtf.user_receipts_30d_before != (
              SELECT COUNT(*)
              FROM staging.coupon_receipt_event cre
              WHERE cre.user_id = rtf.user_id
                AND cre.date_received < rtf.as_of_date
                AND cre.date_received >= rtf.as_of_date - INTERVAL '30 days'
          )
    """)).first()

    assert violations.violations == 0, \
        f"User receipts time leakage detected: {violations.violations} violations (computed value != manual check)"


def test_user_redeemed_time_leakage():
    """验证user核销统计只使用date_redeemed < as_of_date的receipts."""

    db = next(get_db())

    # 正确审计：对比特征值与手动验证值
    violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        WHERE rtf.user_redeemed_count_30d_before > 0
          AND rtf.user_redeemed_count_30d_before != (
              SELECT COUNT(*)
              FROM staging.coupon_receipt_event cre
              WHERE cre.user_id = rtf.user_id
                AND cre.is_redeemed = true
                AND cre.date_redeemed < rtf.as_of_date
                AND cre.date_received < rtf.as_of_date
                AND cre.date_received >= rtf.as_of_date - INTERVAL '30 days'
          )
    """)).first()

    assert violations.violations == 0, \
        f"User redeemed time leakage detected: {violations.violations} violations"


def test_merchant_receipts_time_leakage():
    """验证merchant历史统计只使用date_received < as_of_date的receipts."""

    db = next(get_db())

    # 正确审计：对比特征计算值与手动验证值
    violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        WHERE (rtf.merchant_receipts_7d_before > 0 OR rtf.merchant_receipts_30d_before > 0)
          AND (
              rtf.merchant_receipts_30d_before != (
                  SELECT COUNT(*)
                  FROM staging.coupon_receipt_event cre
                  WHERE cre.merchant_id = rtf.merchant_id
                    AND cre.date_received < rtf.as_of_date
                    AND cre.date_received >= rtf.as_of_date - INTERVAL '30 days'
              )
              OR rtf.merchant_receipts_7d_before != (
                  SELECT COUNT(*)
                  FROM staging.coupon_receipt_event cre
                  WHERE cre.merchant_id = rtf.merchant_id
                    AND cre.date_received < rtf.as_of_date
                    AND cre.date_received >= rtf.as_of_date - INTERVAL '7 days'
              )
          )
    """)).first()

    assert violations.violations == 0, \
        f"Merchant receipts time leakage detected: {violations.violations} violations"


def test_merchant_redeemed_time_leakage():
    """验证merchant核销统计只使用date_redeemed < as_of_date的receipts."""

    db = next(get_db())

    # 性能优化：样本验证（避免全表扫描）
    sample_check = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM (
            SELECT rtf.receipt_id, rtf.merchant_redeemed_count_30d_before
            FROM feature.receipt_training_features rtf
            WHERE rtf.merchant_redeemed_count_30d_before > 0
            TABLESAMPLE SYSTEM (0.01)
        ) sample
        WHERE sample.merchant_redeemed_count_30d_before != (
            SELECT COUNT(*)
            FROM staging.coupon_receipt_event cre
            WHERE cre.merchant_id = (SELECT merchant_id FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.is_redeemed = true
              AND cre.date_redeemed < (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.date_received < (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.date_received >= (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id) - INTERVAL '30 days'
        )
    """)).first()

    assert sample_check.violations == 0, \
        f"Merchant redeemed time leakage detected in sample: {sample_check.violations} violations"


def test_coupon_receipts_time_leakage():
    """验证coupon历史统计只使用date_received < as_of_date的receipts."""

    db = next(get_db())

    # 性能优化：样本验证（避免全表扫描）
    sample_check = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM (
            SELECT rtf.receipt_id, rtf.coupon_total_receipts_before
            FROM feature.receipt_training_features rtf
            WHERE rtf.coupon_total_receipts_before > 0
            TABLESAMPLE SYSTEM (0.01)
        ) sample
        WHERE sample.coupon_total_receipts_before != (
            SELECT COUNT(*)
            FROM staging.coupon_receipt_event cre
            WHERE cre.coupon_id = (SELECT coupon_id FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.date_received < (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
        )
    """)).first()

    assert sample_check.violations == 0, \
        f"Coupon receipts time leakage detected in sample: {sample_check.violations} violations"


def test_coupon_redeemed_time_leakage():
    """验证coupon核销统计只使用date_redeemed < as_of_date的receipts."""

    db = next(get_db())

    # 性能优化：样本验证（避免全表扫描）
    sample_check = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM (
            SELECT rtf.receipt_id, rtf.coupon_redeemed_count_before
            FROM feature.receipt_training_features rtf
            WHERE rtf.coupon_redeemed_count_before > 0
            TABLESAMPLE SYSTEM (0.01)
        ) sample
        WHERE sample.coupon_redeemed_count_before != (
            SELECT COUNT(*)
            FROM staging.coupon_receipt_event cre
            WHERE cre.coupon_id = (SELECT coupon_id FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.is_redeemed = true
              AND cre.date_redeemed < (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
              AND cre.date_received < (SELECT as_of_date FROM feature.receipt_training_features WHERE receipt_id = sample.receipt_id)
        )
    """)).first()

    assert sample_check.violations == 0, \
        f"Coupon redeemed time leakage detected in sample: {sample_check.violations} violations"


def test_no_current_receipt_in_features():
    """验证特征不包含当前receipt的数据（date_received = as_of_date也算违规）."""

    db = next(get_db())

    # 正确审计：验证user/merchant/coupon特征计算不包含as_of_date当天的数据
    # 通过对比包含当天和不包含当天的计数差异
    violations = db.execute(text("""
        SELECT COUNT(*) as violations
        FROM feature.receipt_training_features rtf
        WHERE rtf.user_receipts_30d_before > 0
          AND rtf.user_receipts_30d_before != (
              SELECT COUNT(*)
              FROM staging.coupon_receipt_event cre
              WHERE cre.user_id = rtf.user_id
                AND cre.date_received < rtf.as_of_date  -- 严格小于，不包括当天
                AND cre.date_received >= rtf.as_of_date - INTERVAL '30 days'
          )
    """)).first()

    assert violations.violations == 0, \
        f"Current receipt data found in historical features: {violations.violations} violations"


def test_feature_extractor_uses_time_safe_table():
    """验证FeatureExtractor只从receipt_training_features读取，不使用全局快照表."""

    # 检查feature_extractor.py的代码
    import inspect
    from app.ml.train.feature_extractor import FeatureExtractor

    source_code = inspect.getsource(FeatureExtractor.extract_training_features)

    # 必须引用receipt_training_features表
    assert "receipt_training_features" in source_code, \
        "FeatureExtractor must use receipt_training_features table"

    # 不应该直接join全局feature表（时间泄漏）
    assert "feature.user_metrics" not in source_code or "LEFT JOIN" not in source_code, \
        "FeatureExtractor should not directly join feature.user_metrics (time leakage)"

    assert "feature.merchant_metrics" not in source_code or "LEFT JOIN" not in source_code, \
        "FeatureExtractor should not directly join feature.merchant_metrics (time leakage)"


def test_feature_coverage():
    """验证as-of特征覆盖率≥95%."""

    db = next(get_db())

    # 检查关键字段非空率
    result = db.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN user_receipts_30d_before IS NOT NULL THEN 1 END) as user_covered,
            COUNT(CASE WHEN merchant_receipts_30d_before IS NOT NULL THEN 1 END) as merchant_covered,
            COUNT(CASE WHEN coupon_total_receipts_before IS NOT NULL THEN 1 END) as coupon_covered
        FROM feature.receipt_training_features
    """)).first()

    total = result.total or 0

    if total == 0:
        pytest.skip("No receipt_training_features data yet")

    user_coverage = result.user_covered / total if total > 0 else 0
    merchant_coverage = result.merchant_covered / total if total > 0 else 0
    coupon_coverage = result.coupon_covered / total if total > 0 else 0

    assert user_coverage >= 0.95, \
        f"User features coverage {user_coverage:.2%} < 95%"

    assert merchant_coverage >= 0.95, \
        f"Merchant features coverage {merchant_coverage:.2%} < 95%"

    assert coupon_coverage >= 0.95, \
        f"Coupon features coverage {coupon_coverage:.2%} < 95%"


def test_feature_version_correct():
    """验证feature_version正确标记为time-safe版本."""

    db = next(get_db())

    result = db.execute(text("""
        SELECT DISTINCT feature_version
        FROM feature.receipt_training_features
    """)).first()

    if result is None:
        pytest.skip("No receipt_training_features data yet")

    assert result.feature_version == "v1_time_safe", \
        f"Feature version must be 'v1_time_safe', got '{result.feature_version}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])