"""Quick feature computation for testing - compute only essential data."""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import get_db


def compute_features_test_subset():
    """Compute features only for test period + recent training data."""

    db = next(get_db())

    print("Clearing existing features...")
    db.execute(text("TRUNCATE TABLE feature.receipt_training_features"))
    db.commit()

    # Compute features for May-June 2016 only (test period + validation)
    print("Computing features for May-June 2016...")

    # Use simpler SQL with fewer correlated subqueries
    # First compute base features, then add historical features

    query = text("""
        INSERT INTO feature.receipt_training_features
        WITH user_stats AS (
            SELECT
                user_id,
                date_received,
                COUNT(*) OVER (
                    PARTITION BY user_id
                    ORDER BY date_received
                    RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as user_receipts_30d,
                SUM(CASE WHEN is_redeemed THEN 1 ELSE 0 END) OVER (
                    PARTITION BY user_id
                    ORDER BY date_received
                    RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as user_redeemed_30d,
                AVG(CASE WHEN distance >= 0 THEN distance ELSE NULL END) OVER (
                    PARTITION BY user_id
                    ORDER BY date_received
                    RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as user_avg_dist
            FROM staging.coupon_receipt_event
            WHERE date_received >= '2016-04-15'
        ),
        merchant_stats AS (
            SELECT
                merchant_id,
                date_received,
                COUNT(*) OVER (
                    PARTITION BY merchant_id
                    ORDER BY date_received
                    RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as merchant_receipts_30d,
                SUM(CASE WHEN is_redeemed THEN 1 ELSE 0 END) OVER (
                    PARTITION BY merchant_id
                    ORDER BY date_received
                    RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as merchant_redeemed_30d
            FROM staging.coupon_receipt_event
            WHERE date_received >= '2016-04-15'
        ),
        coupon_stats AS (
            SELECT
                coupon_id,
                date_received,
                COUNT(*) OVER (
                    PARTITION BY coupon_id
                    ORDER BY date_received
                    RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as coupon_receipts,
                SUM(CASE WHEN is_redeemed THEN 1 ELSE 0 END) OVER (
                    PARTITION BY coupon_id
                    ORDER BY date_received
                    RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL '1 day' PRECEDING
                ) as coupon_redeemed
            FROM staging.coupon_receipt_event
            WHERE date_received >= '2016-04-15'
        )
        SELECT
            user_id || '_' || merchant_id || '_' || coupon_id || '_' || to_char(cre.date_received, 'YYYYMMDD') || '_' || cre.id as receipt_id,
            cre.user_id,
            cre.merchant_id,
            cre.coupon_id,
            cre.date_received as as_of_date,

            COALESCE(us.user_receipts_30d, 0) as user_receipts_30d_before,
            COALESCE(us.user_redeemed_30d, 0) as user_redeemed_count_30d_before,
            CASE WHEN COALESCE(us.user_receipts_30d, 0) > 0
                THEN COALESCE(us.user_redeemed_30d, 0)::FLOAT / us.user_receipts_30d
                ELSE 0.0
            END as user_redeemed_rate_30d_before,
            COALESCE(us.user_avg_dist, 0.0) as user_avg_distance_before,

            0 as merchant_receipts_7d_before,
            0 as merchant_redeemed_count_7d_before,
            0.0 as merchant_redeemed_rate_7d_before,

            COALESCE(ms.merchant_receipts_30d, 0) as merchant_receipts_30d_before,
            COALESCE(ms.merchant_redeemed_30d, 0) as merchant_redeemed_count_30d_before,
            CASE WHEN COALESCE(ms.merchant_receipts_30d, 0) > 0
                THEN COALESCE(ms.merchant_redeemed_30d, 0)::FLOAT / ms.merchant_receipts_30d
                ELSE 0.0
            END as merchant_redeemed_rate_30d_before,
            0.0 as merchant_avg_discount_depth_before,

            COALESCE(cs.coupon_receipts, 0) as coupon_total_receipts_before,
            COALESCE(cs.coupon_redeemed, 0) as coupon_redeemed_count_before,
            CASE WHEN COALESCE(cs.coupon_receipts, 0) > 0
                THEN COALESCE(cs.coupon_redeemed, 0)::FLOAT / cs.coupon_receipts
                ELSE 0.0
            END as coupon_redeemed_rate_before,
            0.0 as coupon_avg_redeem_days_before,

            CASE
                WHEN cre.discount_rate LIKE '%:%' THEN '满减'
                WHEN cre.discount_rate ~ '^[0-9.]+$' THEN '折扣'
                ELSE '未知'
            END as discount_type,

            CASE
                WHEN cre.discount_rate LIKE '%:%' THEN
                    CAST(SPLIT_PART(cre.discount_rate, ':', 2) AS FLOAT) /
                    CAST(SPLIT_PART(cre.discount_rate, ':', 1) AS FLOAT)
                WHEN cre.discount_rate ~ '^[0-9.]+$' THEN
                    1.0 - CAST(cre.discount_rate AS FLOAT)
                ELSE 0.0
            END as discount_value,

            CASE
                WHEN cre.discount_rate LIKE '%:%' THEN CAST(SPLIT_PART(cre.discount_rate, ':', 1) AS FLOAT)
                ELSE 0.0
            END as threshold_amount,

            CASE
                WHEN cre.discount_rate LIKE '%:%' THEN CAST(SPLIT_PART(cre.discount_rate, ':', 2) AS FLOAT)
                ELSE 0.0
            END as discount_amount,

            COALESCE(cre.distance, -1) as distance,

            EXTRACT(DOW FROM cre.date_received) as day_of_week,
            EXTRACT(MONTH FROM cre.date_received) as month,
            EXTRACT(DAY FROM cre.date_received) as day_of_month,

            cre.is_redeemed as label_is_redeemed,
            'v1_time_safe' as feature_version,
            CURRENT_TIMESTAMP as computed_at

        FROM staging.coupon_receipt_event cre
        LEFT JOIN user_stats us ON cre.user_id = us.user_id AND cre.date_received = us.date_received
        LEFT JOIN merchant_stats ms ON cre.merchant_id = ms.merchant_id AND cre.date_received = ms.date_received
        LEFT JOIN coupon_stats cs ON cre.coupon_id = cs.coupon_id AND cre.date_received = cs.date_received
        WHERE cre.date_received >= '2016-04-15'
        ORDER BY cre.date_received
    """)

    print("Executing optimized SQL...")
    db.execute(query)
    db.commit()

    # Verify
    result = db.execute(text("""
        SELECT COUNT(*) as count,
               MIN(as_of_date) as min_date,
               MAX(as_of_date) as max_date,
               COUNT(DISTINCT user_id) as users,
               COUNT(DISTINCT merchant_id) as merchants
        FROM feature.receipt_training_features
    """)).first()

    print(f"\nComputed features:")
    print(f"  Count: {result.count}")
    print(f"  Date range: {result.min_date} to {result.max_date}")
    print(f"  Users: {result.users}")
    print(f"  Merchants: {result.merchants}")

    db.close()
    return result.count


if __name__ == "__main__":
    compute_features_test_subset()