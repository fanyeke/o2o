"""Data cleaning service for transforming raw data to staging events."""

from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.domain.raw.offline_train import OfflineTrain
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.domain.staging.consumption_event import ConsumptionEvent


class DataCleaningService:
    """Service for cleaning and transforming raw data to staging events."""

    def __init__(self, db: Session):
        """Initialize service with database session.

        Args:
            db: SQLAlchemy session for database operations
        """
        self.db = db

    def transform_to_coupon_receipt_event(
        self, batch_size: int = 10000
    ) -> List[dict]:
        """Transform raw offline_train data to coupon receipt events.

        Each record in offline_train represents a coupon receipt event.
        Calculate is_redeemed based on date field (not null and within 15 days).
        Calculate redeem_days as the difference between date and date_received.
        Handle null distance values by setting to -1.

        Args:
            batch_size: Number of records to process in each batch

        Returns:
            List of dictionaries suitable for bulk insert
        """
        events = []

        # Query all records from raw.offline_train using mappings for dict access
        result = self.db.execute(
            text("SELECT * FROM raw.offline_train ORDER BY id")
        ).mappings()

        for row in result:
            # Parse date_received (required field)
            date_received = self._parse_date(row["date_received"])
            if date_received is None:
                continue  # Skip invalid records

            # Parse distance, handle null/empty values
            distance = self._parse_distance(row["distance"])

            # Determine if coupon was redeemed
            date_redeemed = self._parse_date(row["date"])
            is_redeemed = False
            redeem_days = None

            if date_redeemed is not None:
                # Calculate days between receipt and redemption
                delta = (date_redeemed - date_received).days
                # Only count as redeemed if within 15 days
                if 0 <= delta <= 15:
                    is_redeemed = True
                    redeem_days = delta

            event_dict = {
                "user_id": row["user_id"],
                "merchant_id": row["merchant_id"],
                "coupon_id": row["coupon_id"],
                "discount_rate": row["discount_rate"],
                "distance": distance,
                "date_received": date_received,
                "is_redeemed": is_redeemed,
                "date_redeemed": date_redeemed if is_redeemed else None,
                "redeem_days": redeem_days if is_redeemed else None,
            }
            events.append(event_dict)

            # Process in batches
            if len(events) >= batch_size:
                yield events
                events = []

        # Yield remaining events
        if events:
            yield events

    def transform_to_consumption_event(
        self, batch_size: int = 10000
    ) -> List[dict]:
        """Transform raw offline_train data to consumption events.

        Only records with non-null date field are consumption events.
        Associate with coupon_id from the same record.
        Simulate amount field based on discount (estimated).

        Args:
            batch_size: Number of records to process in each batch

        Returns:
            List of dictionaries suitable for bulk insert
        """
        events = []

        # Query records where date is not null (consumption occurred) using mappings
        result = self.db.execute(
            text("SELECT * FROM raw.offline_train WHERE date IS NOT NULL AND date != '' ORDER BY id")
        ).mappings()

        for row in result:
            # Parse date (required for consumption event)
            consumption_date = self._parse_date(row["date"])
            if consumption_date is None:
                continue  # Skip invalid records

            # Simulate amount based on discount_rate
            amount = self._simulate_amount(row["discount_rate"])

            event_dict = {
                "user_id": row["user_id"],
                "merchant_id": row["merchant_id"],
                "coupon_id": row["coupon_id"] if row["coupon_id"] else None,
                "discount_rate": row["discount_rate"],
                "date": consumption_date,
                "amount": amount,
            }
            events.append(event_dict)

            # Process in batches
            if len(events) >= batch_size:
                yield events
                events = []

        # Yield remaining events
        if events:
            yield events

    def clean_all_data(self, batch_size: int = 10000) -> dict:
        """Clean all data from raw to staging layer.

        Args:
            batch_size: Number of records to process in each batch

        Returns:
            Dictionary with count of processed events
        """
        # Truncate existing staging tables
        self.db.execute(text("TRUNCATE TABLE staging.coupon_receipt_event"))
        self.db.execute(text("TRUNCATE TABLE staging.consumption_event"))
        self.db.commit()

        # Process coupon receipt events
        receipt_count = 0
        for batch in self.transform_to_coupon_receipt_event(batch_size):
            self.db.bulk_insert_mappings(CouponReceiptEvent, batch)
            self.db.commit()
            receipt_count += len(batch)

        # Process consumption events
        consumption_count = 0
        for batch in self.transform_to_consumption_event(batch_size):
            self.db.bulk_insert_mappings(ConsumptionEvent, batch)
            self.db.commit()
            consumption_count += len(batch)

        return {
            "receipt_events": receipt_count,
            "consumption_events": consumption_count,
        }

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object.

        Args:
            date_str: Date string in format YYYY-MM-DD or YYYYMMDD

        Returns:
            Date object or None if invalid
        """
        if not date_str or date_str.strip() == "":
            return None
        try:
            date_str = date_str.strip()
            # Try YYYY-MM-DD format first
            if "-" in date_str:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            # Try YYYYMMDD format
            else:
                return datetime.strptime(date_str, "%Y%m%d").date()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _parse_distance(distance_str: Optional[str]) -> float:
        """Parse distance string to float, handling null values.

        Args:
            distance_str: Distance string or null

        Returns:
            Float distance or -1 for null/invalid values
        """
        if not distance_str or distance_str.strip() == "":
            return -1.0
        try:
            return float(distance_str.strip())
        except (ValueError, AttributeError):
            return -1.0

    @staticmethod
    def _simulate_amount(discount_rate: Optional[str]) -> Optional[float]:
        """Simulate consumption amount based on discount rate.

        This is a placeholder implementation since the original dataset
        does not include actual transaction amounts.

        Args:
            discount_rate: Discount rate string (e.g., "200:50" or "0.9")

        Returns:
            Simulated amount or None
        """
        if not discount_rate or discount_rate.strip() == "":
            return None

        try:
            discount_str = discount_rate.strip()

            # Check if it's a "threshold:discount" format (e.g., "200:50")
            if ":" in discount_str:
                parts = discount_str.split(":")
                if len(parts) == 2:
                    threshold = float(parts[0])
                    discount = float(parts[1])
                    # Estimate amount as threshold + some margin
                    return threshold * 1.5
            else:
                # It's a discount rate (e.g., "0.9" means 10% off)
                rate = float(discount_str)
                # Estimate amount based on typical transaction
                # Assume average transaction is 100-500
                return 200.0
        except (ValueError, AttributeError):
            return None

        return None