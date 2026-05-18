"""Quick validation script for user feature calculation.

This script demonstrates the usage of calculate_user_metrics function.
Run this after setting up the database and importing data.
"""
from datetime import date
from app.core.database import SessionLocal
from app.features.user_features import calculate_user_metrics


def main():
    """Validate user feature calculation with sample data."""
    db = SessionLocal()
    try:
        # Calculate user metrics for a specific reference date
        reference_date = date(2026, 5, 17)
        print(f"Calculating user metrics for reference date: {reference_date}")
        print(f"30-day window: {reference_date - __import__('datetime').timedelta(days=29)} to {reference_date}")

        # Execute calculation
        user_metrics_list = calculate_user_metrics(
            db=db,
            reference_date=reference_date,
            batch_size=1000
        )

        print(f"\nCalculated metrics for {len(user_metrics_list)} users")

        # Display sample results (first 5 users)
        print("\nSample results (first 5 users):")
        print("-" * 100)
        print(f"{'User ID':<15} {'Total Receipts':<15} {'Redeemed':<12} {'Rate':<10} {'Avg Distance':<15} {'Last Receipt'}")
        print("-" * 100)

        for metrics in user_metrics_list[:5]:
            print(
                f"{metrics.user_id:<15} "
                f"{metrics.total_receipts_30d or 0:<15} "
                f"{metrics.redeemed_count_30d or 0:<12} "
                f"{metrics.redeemed_rate_30d or 0:<10.2f} "
                f"{metrics.avg_distance or 'N/A':<15} "
                f"{metrics.last_receipt_date or 'N/A'}"
            )

        print(f"\nMetrics calculation completed successfully!")
        print(f"Timestamp: {user_metrics_list[0].updated_at if user_metrics_list else 'N/A'}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()