"""SQL-based time-safe feature computation for faster processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import get_db


def compute_features_sql():
    """Compute time-safe features using efficient SQL queries."""

    db = next(get_db())

    print("Clearing existing features...")
    db.execute(text("TRUNCATE TABLE feature.receipt_training_features"))
    db.commit()

    print("Computing features using SQL...")

    # Use a single SQL query with window functions to compute all features
    # This is much faster than Python loops

    query = text("""
        INSERT INTO feature.receipt_training_features
        SELECT
            -- Receipt ID (unique per receipt)
            user_id || '_' || merchant_id || '_' || coupon_id || '_' || to_char(date_received, 'YYYYMMDD') || '_' || id as receipt_id,
            user_id,
            merchant_id,
            coupon_id,
            date_received as as_of_date,

            -- User historical features (computed using data BEFORE date_received)
            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.user_id = cre.user_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
            ) as user_receipts_30d_before,

            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.user_id = cre.user_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
                  AND cre2.is_redeemed = true
                  AND cre2.date_redeemed < cre.date_received
            ) as user_redeemed_count_30d_before,

            (
                SELECT CASE WHEN COUNT(*) > 0
                    THEN COUNT(CASE WHEN is_redeemed = true AND date_redeemed < cre.date_received THEN 1 END)::FLOAT / COUNT(*)
                    ELSE 0.0 END
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.user_id = cre.user_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
            ) as user_redeemed_rate_30d_before,

            (
                SELECT AVG(CASE WHEN distance >= 0 THEN distance ELSE NULL END)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.user_id = cre.user_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
            ) as user_avg_distance_before,

            -- Merchant historical features
            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '7 days'
            ) as merchant_receipts_7d_before,

            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '7 days'
                  AND cre2.is_redeemed = true
                  AND cre2.date_redeemed < cre.date_received
            ) as merchant_redeemed_count_7d_before,

            (
                SELECT CASE WHEN COUNT(*) > 0
                    THEN COUNT(CASE WHEN is_redeemed = true AND date_redeemed < cre.date_received THEN 1 END)::FLOAT / COUNT(*)
                    ELSE 0.0 END
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '7 days'
            ) as merchant_redeemed_rate_7d_before,

            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
            ) as merchant_receipts_30d_before,

            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
                  AND cre2.is_redeemed = true
                  AND cre2.date_redeemed < cre.date_received
            ) as merchant_redeemed_count_30d_before,

            (
                SELECT CASE WHEN COUNT(*) > 0
                    THEN COUNT(CASE WHEN is_redeemed = true AND date_redeemed < cre.date_received THEN 1 END)::FLOAT / COUNT(*)
                    ELSE 0.0 END
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.date_received >= cre.date_received - INTERVAL '30 days'
            ) as merchant_redeemed_rate_30d_before,

            (
                SELECT AVG(CASE
                    WHEN discount_rate LIKE '%:%' THEN
                        CAST(SPLIT_PART(discount_rate, ':', 2) AS FLOAT) /
                        CAST(SPLIT_PART(discount_rate, ':', 1) AS FLOAT)
                    WHEN discount_rate ~ '^[0-9.]+$' THEN
                        1.0 - CAST(discount_rate AS FLOAT)
                    ELSE NULL
                END)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.merchant_id = cre.merchant_id
                  AND cre2.date_received < cre.date_received
            ) as merchant_avg_discount_depth_before,

            -- Coupon historical features
            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.coupon_id = cre.coupon_id
                  AND cre2.date_received < cre.date_received
            ) as coupon_total_receipts_before,

            (
                SELECT COUNT(*)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.coupon_id = cre.coupon_id
                  AND cre2.date_received < cre.date_received
                  AND cre2.is_redeemed = true
                  AND cre2.date_redeemed < cre.date_received
            ) as coupon_redeemed_count_before,

            (
                SELECT CASE WHEN COUNT(*) > 0
                    THEN COUNT(CASE WHEN is_redeemed = true AND date_redeemed < cre.date_received THEN 1 END)::FLOAT / COUNT(*)
                    ELSE 0.0 END
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.coupon_id = cre.coupon_id
                  AND cre2.date_received < cre.date_received
            ) as coupon_redeemed_rate_before,

            (
                SELECT AVG(CASE WHEN is_redeemed = true AND date_redeemed < cre.date_received
                    THEN date_redeemed - date_received ELSE NULL END)
                FROM staging.coupon_receipt_event cre2
                WHERE cre2.coupon_id = cre.coupon_id
                  AND cre2.date_received < cre.date_received
            ) as coupon_avg_redeem_days_before,

            -- Static features
            CASE
                WHEN discount_rate LIKE '%:%' THEN '满减'
                WHEN discount_rate ~ '^[0-9.]+$' THEN '折扣'
                ELSE '未知'
            END as discount_type,

            CASE
                WHEN discount_rate LIKE '%:%' THEN
                    CAST(SPLIT_PART(discount_rate, ':', 2) AS FLOAT) /
                    CAST(SPLIT_PART(discount_rate, ':', 1) AS FLOAT)
                WHEN discount_rate ~ '^[0-9.]+$' THEN
                    1.0 - CAST(discount_rate AS FLOAT)
                ELSE 0.0
            END as discount_value,

            CASE
                WHEN discount_rate LIKE '%:%' THEN CAST(SPLIT_PART(discount_rate, ':', 1) AS FLOAT)
                ELSE 0.0
            END as threshold_amount,

            CASE
                WHEN discount_rate LIKE '%:%' THEN CAST(SPLIT_PART(discount_rate, ':', 2) AS FLOAT)
                ELSE 0.0
            END as discount_amount,

            COALESCE(distance, -1) as distance,

            -- Time features
            EXTRACT(DOW FROM date_received) as day_of_week,
            EXTRACT(MONTH FROM date_received) as month,
            EXTRACT(DAY FROM date_received) as day_of_month,

            -- Target label
            is_redeemed as label_is_redeemed,

            'v1_time_safe' as feature_version,
            CURRENT_TIMESTAMP as computed_at

        FROM staging.coupon_receipt_event cre
        ORDER BY date_received
    """)

    # Execute in batches to avoid memory issues
    print("Executing SQL feature computation (this may take several minutes)...")

    try:
        db.execute(query)
        db.commit()
        print("SQL computation completed!")

        # Verify results
        result = db.execute(text("""
            SELECT COUNT(*) as count,
                   MIN(as_of_date) as min_date,
                   MAX(as_of_date) as max_date
            FROM feature.receipt_training_features
        """)).first()

        print(f"Computed features for {result.count} receipts")
        print(f"Date range: {result.min_date} to {result.max_date}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise

    db.close()


if __name__ == "__main__":
    compute_features_sql()