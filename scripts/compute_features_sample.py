#!/usr/bin/env python3
"""Compute sample time-safe features - simplified version."""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compute_sample_features(start_date: date, end_date: date):
    db = next(get_db())

    logger.info(f"Computing sample: {start_date} to {end_date}")

    db.execute(text("DELETE FROM feature.receipt_training_features WHERE as_of_date BETWEEN :s AND :e"), {"s": start_date, "e": end_date})
    db.commit()

    sql = text("""
        WITH targets AS (
            SELECT user_id, merchant_id, coupon_id, date_received, date_redeemed, is_redeemed, distance, id
            FROM staging.coupon_receipt_event
            WHERE date_received BETWEEN :s AND :e
            ORDER BY date_received, user_id
            LIMIT 20000
        )
        INSERT INTO feature.receipt_training_features (
            receipt_id, user_id, merchant_id, coupon_id, as_of_date,
            user_receipts_30d_before, user_redeemed_count_30d_before, user_redeemed_rate_30d_before, user_avg_distance_before,
            merchant_receipts_7d_before, merchant_redeemed_count_7d_before, merchant_redeemed_rate_7d_before,
            merchant_receipts_30d_before, merchant_redeemed_count_30d_before, merchant_redeemed_rate_30d_before, merchant_avg_discount_depth_before,
            coupon_total_receipts_before, coupon_redeemed_count_before, coupon_redeemed_rate_before, coupon_avg_redeem_days_before,
            discount_type, discount_value, threshold_amount, discount_amount, distance,
            day_of_week, month, day_of_month, label_is_redeemed, feature_version
        )
        SELECT
            t.user_id||'_'||t.merchant_id||'_'||t.coupon_id||'_'||to_char(t.date_received,'YYYYMMDD')||'_'||t.id,
            t.user_id, t.merchant_id, t.coupon_id, t.date_received,
            u.cnt, u.red_cnt, u.red_rate, u.avg_dist,
            m.cnt7, m.red7, m.rate7,
            m.cnt30, m.red30, m.rate30, m.avg_depth,
            c.cnt, c.red_cnt, c.red_rate, c.avg_days,
            'unknown', 0.0, 0.0, 0.0,
            COALESCE(t.distance::integer, 0),
            EXTRACT(DOW FROM t.date_received)::integer,
            EXTRACT(MONTH FROM t.date_received)::integer,
            EXTRACT(DAY FROM t.date_received)::integer,
            t.is_redeemed, 'v1_time_safe'
        FROM targets t,
        LATERAL (SELECT COUNT(*) cnt, COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received) red_cnt,
                 CASE WHEN COUNT(*)>0 THEN COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received)::float/COUNT(*) ELSE 0 END red_rate,
                 COALESCE(AVG(distance),0) avg_dist
                 FROM staging.coupon_receipt_event WHERE user_id=t.user_id AND date_received<t.date_received AND date_received>=t.date_received-INTERVAL'30 days') u,
        LATERAL (SELECT COUNT(*) FILTER(WHERE date_received>=t.date_received-INTERVAL'7 days') cnt7,
                 COUNT(*) FILTER(WHERE date_received>=t.date_received-INTERVAL'7 days' AND is_redeemed AND date_redeemed<t.date_received) red7,
                 CASE WHEN COUNT(*) FILTER(WHERE date_received>=t.date_received-INTERVAL'7 days')>0 THEN
                      COUNT(*) FILTER(WHERE date_received>=t.date_received-INTERVAL'7 days' AND is_redeemed AND date_redeemed<t.date_received)::float/COUNT(*) FILTER(WHERE date_received>=t.date_received-INTERVAL'7 days')
                 ELSE 0 END rate7,
                 COUNT(*) cnt30, COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received) red30,
                 CASE WHEN COUNT(*)>0 THEN COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received)::float/COUNT(*) ELSE 0 END rate30,
                 0 avg_depth
                 FROM staging.coupon_receipt_event WHERE merchant_id=t.merchant_id AND date_received<t.date_received AND date_received>=t.date_received-INTERVAL'30 days') m,
        LATERAL (SELECT COUNT(*) cnt, COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received) red_cnt,
                 CASE WHEN COUNT(*)>0 THEN COUNT(*) FILTER(WHERE is_redeemed AND date_redeemed<t.date_received)::float/COUNT(*) ELSE 0 END red_rate,
                 COALESCE(AVG(CASE WHEN is_redeemed AND date_redeemed<t.date_received THEN date_redeemed-date_received END),0) avg_days
                 FROM staging.coupon_receipt_event WHERE coupon_id=t.coupon_id AND date_received<t.date_received) c
    """)

    result = db.execute(sql, {"s": start_date, "e": end_date})
    rows = result.rowcount
    db.commit()

    logger.info(f"✓ Inserted {rows} rows")

    count = db.execute(text("SELECT COUNT(*) FROM feature.receipt_training_features")).first()[0]
    logger.info(f"Total: {count} rows")

    db.close()
    return rows

if __name__ == "__main__":
    compute_sample_features(date(2016,6,1), date(2016,6,7))
    print("✓ Done")