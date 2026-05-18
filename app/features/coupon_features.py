"""Coupon-level feature engineering.

This module calculates aggregated metrics for coupons from staging layer events.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func, Integer, Float

from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.feature.coupon_metrics import CouponMetrics


def parse_discount(discount_rate: str) -> Dict[str, Any]:
    """Parse discount rate string into structured discount information.

    Args:
        discount_rate: Discount description (e.g., "200:50" for 满减, "0.9" for 折扣)

    Returns:
        Dictionary with discount_type, threshold_amount, discount_amount, discount_value

    Examples:
        >>> parse_discount("200:50")
        {'discount_type': '满减', 'threshold_amount': 200.0, 'discount_amount': 50.0, 'discount_value': 0.25}

        >>> parse_discount("0.9")
        {'discount_type': '折扣', 'discount_value': 0.1}
    """
    if not discount_rate:
        return {
            'discount_type': None,
            'threshold_amount': None,
            'discount_amount': None,
            'discount_value': None
        }

    if ':' in discount_rate:
        # 满减券格式: threshold:discount
        parts = discount_rate.split(':')
        if len(parts) != 2:
            return {
                'discount_type': None,
                'threshold_amount': None,
                'discount_amount': None,
                'discount_value': None
            }

        try:
            threshold = float(parts[0])
            discount = float(parts[1])
            return {
                'discount_type': '满减',
                'threshold_amount': threshold,
                'discount_amount': discount,
                'discount_value': discount / threshold if threshold > 0 else 0.0
            }
        except (ValueError, ZeroDivisionError):
            return {
                'discount_type': None,
                'threshold_amount': None,
                'discount_amount': None,
                'discount_value': None
            }
    else:
        # 折扣券格式: discount rate (e.g., 0.9 means 10% off)
        try:
            rate = float(discount_rate)
            return {
                'discount_type': '折扣',
                'discount_value': 1.0 - rate
            }
        except ValueError:
            return {
                'discount_type': None,
                'threshold_amount': None,
                'discount_amount': None,
                'discount_value': None
            }


class CouponFeatureCalculator:
    """Calculator for coupon-level aggregated metrics."""

    def __init__(self, db: Session):
        """Initialize calculator with database session.

        Args:
            db: SQLAlchemy session for database operations
        """
        self.db = db

    def calculate_coupon_metrics(
        self,
        batch_size: int = 1000,
        coupon_ids: Optional[List[str]] = None
    ) -> List[CouponMetrics]:
        """Calculate coupon dimension aggregated metrics.

        Calculates:
        - coupon_id: 优惠券唯一标识
        - merchant_id: 所属商户
        - discount_type: 券类型（"满减" or "折扣"）
        - discount_rate: 原始折扣描述
        - discount_value: 折扣实际值（满减：减免/门槛，折扣：1-折扣率）
        - threshold_amount: 门槛金额（满减券）
        - discount_amount: 减免金额（满减券）
        - total_receipts: 总发券量
        - redeemed_count: 总核销量
        - redeemed_rate: 总核销率
        - avg_redeem_days: 平均核销天数（领券到核销间隔）
        - updated_at: 刷新时间

        Args:
            batch_size: Number of coupons to process in each batch (default: 1000)
            coupon_ids: Optional list of specific coupon IDs to calculate.
                       If None, calculates for all coupons.

        Returns:
            List of CouponMetrics ORM objects (not persisted to database)

        Note:
            - This function creates CouponMetrics objects but does NOT persist them.
              The caller is responsible for saving to database.
            - Uses batch processing to handle large datasets efficiently.
        """
        # Use SQL aggregation for efficient calculation
        query_text = """
            SELECT
                coupon_id,
                merchant_id,
                discount_rate,
                COUNT(*) as total_receipts,
                SUM(CASE WHEN is_redeemed = true THEN 1 ELSE 0 END) as redeemed_count,
                AVG(CASE WHEN is_redeemed = true THEN redeem_days ELSE NULL END) as avg_redeem_days
            FROM staging.coupon_receipt_event
        """

        # Add WHERE clause for specific coupon IDs if provided
        if coupon_ids:
            # Create parameter placeholders for coupon_ids
            placeholders = ", ".join([f":coupon_id_{i}" for i in range(len(coupon_ids))])
            query_text += f" WHERE coupon_id IN ({placeholders})"

        query_text += " GROUP BY coupon_id, merchant_id, discount_rate ORDER BY coupon_id"

        # Build parameters dict
        params = {}
        if coupon_ids:
            for i, coupon_id in enumerate(coupon_ids):
                params[f"coupon_id_{i}"] = coupon_id

        # Execute query
        result = self.db.execute(text(query_text), params).mappings()

        # Process results and create ORM objects
        metrics_list = []
        current_time = datetime.now()

        for row in result:
            # Parse discount information
            discount_info = parse_discount(row["discount_rate"])

            # Calculate redemption rate
            total_receipts = row["total_receipts"] or 0
            redeemed_count = row["redeemed_count"] or 0
            redeemed_rate = (redeemed_count / total_receipts) if total_receipts > 0 else 0.0

            # Create CouponMetrics object
            metrics = CouponMetrics(
                coupon_id=row["coupon_id"],
                merchant_id=row["merchant_id"],
                discount_type=discount_info.get('discount_type'),
                discount_rate=row["discount_rate"],
                discount_value=discount_info.get('discount_value'),
                threshold_amount=discount_info.get('threshold_amount'),
                discount_amount=discount_info.get('discount_amount'),
                total_receipts=total_receipts,
                redeemed_count=redeemed_count,
                redeemed_rate=redeemed_rate,
                avg_redeem_days=row["avg_redeem_days"],
                updated_at=current_time,
            )
            metrics_list.append(metrics)

            # Batch processing: yield and clear when reaching batch size
            if len(metrics_list) >= batch_size:
                yield metrics_list
                metrics_list = []

        # Yield remaining metrics
        if metrics_list:
            yield metrics_list

    def save_coupon_metrics(
        self,
        batch_size: int = 1000,
        coupon_ids: Optional[List[str]] = None
    ) -> dict:
        """Calculate and save coupon metrics to feature layer.

        Args:
            batch_size: Number of coupons to process in each batch
            coupon_ids: Optional list of specific coupon IDs to calculate

        Returns:
            Dictionary with count of processed coupons
        """
        # Clear existing metrics (truncate all or specific coupons)
        if coupon_ids:
            # Delete specific coupons
            placeholders = ", ".join([f":coupon_id_{i}" for i in range(len(coupon_ids))])
            params = {f"coupon_id_{i}": coupon_id for i, coupon_id in enumerate(coupon_ids)}
            self.db.execute(
                text(f"DELETE FROM feature.coupon_metrics WHERE coupon_id IN ({placeholders})"),
                params
            )
        else:
            # Clear all coupon metrics
            self.db.execute(text("TRUNCATE TABLE feature.coupon_metrics"))
        self.db.commit()

        # Process metrics in batches
        coupon_count = 0
        for batch in self.calculate_coupon_metrics(batch_size, coupon_ids):
            # Bulk insert batch
            self.db.bulk_save_objects(batch)
            self.db.commit()
            coupon_count += len(batch)

        return {
            "coupons_processed": coupon_count,
        }


def calculate_coupon_metrics(
    db: Session,
    batch_size: int = 1000,
    coupon_ids: Optional[List[str]] = None
) -> List[CouponMetrics]:
    """Convenience function to calculate coupon metrics.

    This function provides a simple interface for calculating coupon metrics
    without directly instantiating the CouponFeatureCalculator class.

    Args:
        db: SQLAlchemy session for database operations
        batch_size: Number of coupons to process in each batch (default: 1000)
        coupon_ids: Optional list of specific coupon IDs to calculate.
                   If None, calculates for all coupons.

    Returns:
        List of CouponMetrics ORM objects
    """
    calculator = CouponFeatureCalculator(db)
    all_metrics = []

    for batch in calculator.calculate_coupon_metrics(batch_size, coupon_ids):
        all_metrics.extend(batch)

    return all_metrics