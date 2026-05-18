"""Feature calculation module for merchant-level metrics."""

from datetime import datetime, date, timedelta
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.domain.feature.merchant_metrics import MerchantMetrics


class MerchantFeatureCalculator:
    """Calculator for merchant-level aggregated metrics."""

    def __init__(self, db: Session):
        """Initialize calculator with database session.

        Args:
            db: SQLAlchemy session for database operations
        """
        self.db = db

    def calculate_merchant_metrics(
        self, batch_size: int = 1000, reference_date: date = None
    ) -> List[MerchantMetrics]:
        """Calculate merchant dimension aggregated metrics.

        Calculates:
        - total_receipts_7d: 近7日发券总数
        - redeemed_count_7d: 近7日核销数量
        - redeemed_rate_7d: 近7日核销率（除零处理：NULL）
        - total_receipts_30d: 近30日发券总数
        - redeemed_count_30d: 近30日核销数量
        - redeemed_rate_30d: 近30日核销率
        - redeemed_rate_change: 核销率变化幅度 = (rate_7d - rate_30d) / rate_30d
        - avg_discount_depth: 平均折扣深度
        - activity_health_score: 活动健康分（综合评分）
        - last_activity_date: 最后活动日期
        - updated_at: 刷新时间

        Args:
            batch_size: Number of merchants to process in each batch
            reference_date: Reference date for time window calculations (defaults to latest date in data)

        Returns:
            List of MerchantMetrics ORM objects
        """
        # Determine reference date (latest activity date in data)
        if reference_date is None:
            result = self.db.execute(
                text("SELECT MAX(date_received) as max_date FROM staging.coupon_receipt_event")
            ).first()
            reference_date = result.max_date if result and result.max_date else date.today()

        # Calculate time windows
        window_7d_start = reference_date - timedelta(days=7)
        window_30d_start = reference_date - timedelta(days=30)

        # Use SQL aggregation with window functions for efficient calculation
        query = text("""
            WITH merchant_stats AS (
                SELECT
                    merchant_id,
                    -- 7-day window metrics
                    COUNT(CASE WHEN date_received >= :window_7d_start THEN 1 END) as total_receipts_7d,
                    COUNT(CASE WHEN date_received >= :window_7d_start AND is_redeemed = true THEN 1 END) as redeemed_count_7d,
                    -- 30-day window metrics
                    COUNT(CASE WHEN date_received >= :window_30d_start THEN 1 END) as total_receipts_30d,
                    COUNT(CASE WHEN date_received >= :window_30d_start AND is_redeemed = true THEN 1 END) as redeemed_count_30d,
                    -- Overall metrics
                    AVG(CASE
                        WHEN discount_rate LIKE '%:%' THEN
                            CAST(SPLIT_PART(discount_rate, ':', 2) AS FLOAT) /
                            CAST(SPLIT_PART(discount_rate, ':', 1) AS FLOAT)
                        WHEN discount_rate ~ '^[0-9.]+$' THEN
                            1.0 - CAST(discount_rate AS FLOAT)
                        ELSE NULL
                    END) as avg_discount_depth,
                    MAX(date_received) as last_activity_date,
                    -- Additional stats for health score
                    COUNT(DISTINCT coupon_id) as total_coupon_types,
                    STDDEV(CASE WHEN is_redeemed = true THEN 1.0 ELSE 0.0 END) as redeem_stability
                FROM staging.coupon_receipt_event
                GROUP BY merchant_id
            ),
            merchant_rates AS (
                SELECT
                    merchant_id,
                    total_receipts_7d,
                    redeemed_count_7d,
                    CASE
                        WHEN total_receipts_7d > 0 THEN redeemed_count_7d::FLOAT / total_receipts_7d
                        ELSE NULL
                    END as redeemed_rate_7d,
                    total_receipts_30d,
                    redeemed_count_30d,
                    CASE
                        WHEN total_receipts_30d > 0 THEN redeemed_count_30d::FLOAT / total_receipts_30d
                        ELSE NULL
                    END as redeemed_rate_30d,
                    avg_discount_depth,
                    last_activity_date,
                    total_coupon_types,
                    redeem_stability
                FROM merchant_stats
            )
            SELECT
                merchant_id,
                total_receipts_7d,
                redeemed_count_7d,
                redeemed_rate_7d,
                total_receipts_30d,
                redeemed_count_30d,
                redeemed_rate_30d,
                CASE
                    WHEN redeemed_rate_30d IS NOT NULL AND redeemed_rate_30d > 0
                    THEN (redeemed_rate_7d - redeemed_rate_30d) / redeemed_rate_30d
                    ELSE NULL
                END as redeemed_rate_change,
                avg_discount_depth,
                last_activity_date,
                -- Activity health score (normalized composite score)
                CASE
                    WHEN total_receipts_30d > 0 THEN
                        -- Combine: redemption rate (40%), volume (30%), stability (30%)
                        (
                            COALESCE(redeemed_rate_30d, 0) * 0.4 +
                            LEAST(total_receipts_30d::FLOAT / 1000.0, 1.0) * 0.3 +
                            CASE
                                WHEN redeem_stability IS NOT NULL THEN
                                    LEAST(1.0 - redeem_stability, 1.0) * 0.3
                                ELSE 0.3
                            END
                        )
                    ELSE NULL
                END as activity_health_score
            FROM merchant_rates
            ORDER BY merchant_id
        """)

        # Execute query with parameters
        result = self.db.execute(
            query,
            {
                "window_7d_start": window_7d_start,
                "window_30d_start": window_30d_start,
            }
        ).mappings()

        # Process results in batches and create ORM objects
        metrics_list = []
        current_time = datetime.now()

        for row in result:
            metric = MerchantMetrics(
                merchant_id=row["merchant_id"],
                total_receipts_7d=row["total_receipts_7d"],
                redeemed_count_7d=row["redeemed_count_7d"],
                redeemed_rate_7d=row["redeemed_rate_7d"],
                total_receipts_30d=row["total_receipts_30d"],
                redeemed_count_30d=row["redeemed_count_30d"],
                redeemed_rate_30d=row["redeemed_rate_30d"],
                redeemed_rate_change=row["redeemed_rate_change"],
                avg_discount_depth=row["avg_discount_depth"],
                activity_health_score=row["activity_health_score"],
                last_activity_date=row["last_activity_date"],
                updated_at=current_time,
            )
            metrics_list.append(metric)

            # Batch processing: yield and clear when reaching batch size
            if len(metrics_list) >= batch_size:
                yield metrics_list
                metrics_list = []

        # Yield remaining metrics
        if metrics_list:
            yield metrics_list

    def save_merchant_metrics(self, batch_size: int = 1000, reference_date: date = None) -> dict:
        """Calculate and save merchant metrics to feature layer.

        Args:
            batch_size: Number of merchants to process in each batch
            reference_date: Reference date for time window calculations

        Returns:
            Dictionary with count of processed merchants
        """
        # Clear existing metrics
        self.db.execute(text("TRUNCATE TABLE feature.merchant_metrics"))
        self.db.commit()

        # Process metrics in batches
        merchant_count = 0
        for batch in self.calculate_merchant_metrics(batch_size, reference_date):
            # Bulk insert batch
            self.db.bulk_save_objects(batch)
            self.db.commit()
            merchant_count += len(batch)

        return {
            "merchants_processed": merchant_count,
            "reference_date": reference_date or self._get_latest_date(),
        }

    def _get_latest_date(self) -> date:
        """Get latest activity date from coupon receipt events.

        Returns:
            Latest date_received from staging table
        """
        result = self.db.execute(
            text("SELECT MAX(date_received) as max_date FROM staging.coupon_receipt_event")
        ).first()

        if result and result.max_date:
            return result.max_date
        return date.today()


def calculate_merchant_metrics(db: Session, batch_size: int = 1000) -> List[MerchantMetrics]:
    """Convenience function to calculate merchant metrics.

    This function provides a simple interface for calculating merchant metrics
    without directly instantiating the MerchantFeatureCalculator class.

    Args:
        db: SQLAlchemy session for database operations
        batch_size: Number of merchants to process in each batch

    Returns:
        List of MerchantMetrics ORM objects
    """
    calculator = MerchantFeatureCalculator(db)
    all_metrics = []

    for batch in calculator.calculate_merchant_metrics(batch_size):
        all_metrics.extend(batch)

    return all_metrics