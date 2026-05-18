# T030-T031: User Feature Implementation Summary

## Tasks Completed

**T030**: Created `app/features/user_features.py` module
**T031**: Implemented `calculate_user_metrics()` function

## Implementation Details

### Module: `app/features/user_features.py`

**Function**: `calculate_user_metrics(db: Session, reference_date: date = None, batch_size: int = 1000) -> List[UserMetrics]`

**Purpose**: Calculate user-level aggregated metrics from coupon receipt events for the past 30 days.

### Key Features

1. **Time Window Calculation**
   - 30-day window: `reference_date - timedelta(days=29)` to `reference_date`
   - Default: Uses today if `reference_date` not provided

2. **SQL Aggregation Query**
   - Uses SQLAlchemy ORM with aggregation functions
   - Groups by `user_id`
   - Filters by date range (`date_received >= window_start AND date_received <= reference_date`)

3. **Metrics Calculated**
   - `total_receipts_30d`: COUNT of coupon receipts in 30-day window
   - `redeemed_count_30d`: SUM of redeemed coupons (CASE WHEN is_redeemed=True)
   - `redeemed_rate_30d`: `redeemed_count_30d / total_receipts_30d`
     - Division by zero handling: Returns `None` when `total_receipts_30d = 0`
   - `avg_distance`: AVG distance excluding -1 (unknown distance)
     - Uses `CASE WHEN distance = -1 THEN NULL ELSE distance END`
     - Returns `None` if all distances are -1
   - `last_receipt_date`: MAX of `date_received`
   - `updated_at`: Current timestamp for all records

4. **Batch Processing**
   - Default batch size: 1000 users
   - Uses `bulk_save_objects()` for efficient insertion
   - Commits in batches to avoid memory issues

5. **Return Value**
   - Returns list of `UserMetrics` ORM objects
   - Re-queries database to get saved objects with IDs

## Performance Optimizations

1. **Single Query Execution**
   - Uses one SQL query with GROUP BY for all aggregations
   - Avoids N+1 query problem

2. **Batch Insert**
   - Processes 1000 users at a time
   - Uses `bulk_save_objects()` for efficient insertion

3. **Index Utilization**
   - Leverages existing `idx_user_date` index on `(user_id, date_received)`
   - Efficient filtering and grouping

## Testing

**Test File**: `tests/unit/test_user_features.py`

### Test Cases

1. **Basic Metrics Calculation** (`test_calculate_user_metrics_basic`)
   - Tests user with 5 receipts, 3 redeemed
   - Verifies total count, redeemed count, and rate
   - Validates average distance calculation (excludes -1)

2. **All Unknown Distances** (`test_calculate_user_metrics_all_unknown_distances`)
   - Tests user with all distances = -1
   - Verifies `avg_distance = None`

3. **Window Filtering** (`test_calculate_user_metrics_window_filtering`)
   - Tests that events outside 30-day window are excluded

4. **Zero Receipts** (`test_calculate_user_metrics_zero_receipts`)
   - Tests user with no receipts in 30-day window
   - Verifies user not in results

5. **Batch Processing** (`test_calculate_user_metrics_batch_processing`)
   - Tests batch processing with 15 users
   - Validates all users processed correctly

6. **Timestamp Update** (`test_calculate_user_metrics_updated_timestamp`)
   - Verifies `updated_at` field is set correctly

## Usage Example

```python
from datetime import date
from app.core.database import SessionLocal
from app.features.user_features import calculate_user_metrics

# Calculate metrics for specific date
db = SessionLocal()
try:
    metrics = calculate_user_metrics(
        db=db,
        reference_date=date(2026, 5, 17),
        batch_size=1000
    )
    print(f"Calculated metrics for {len(metrics)} users")
finally:
    db.close()
```

## Database Schema

**Table**: `feature.user_metrics`

| Column | Type | Description |
|--------|------|-------------|
| user_id | STRING(64) PK | User identifier |
| total_receipts_30d | INTEGER | Total receipts in 30-day window |
| redeemed_count_30d | INTEGER | Redeemed count in 30-day window |
| redeemed_rate_30d | FLOAT | Redemption rate (NULL if no receipts) |
| avg_distance | FLOAT | Average distance (NULL if all unknown) |
| last_receipt_date | DATE | Last receipt date |
| updated_at | TIMESTAMP | Last update timestamp |

## Next Steps

**T034**: Update `app/tasks/refresh_features.py` to call `calculate_user_metrics()`
**T035**: Integration test for feature calculation
**T049**: Implement `GET /api/v1/metrics/users` API endpoint
**T054-T055**: Create user metrics repository

## Files Created

1. `/home/zzz/project/o2o/app/features/user_features.py` - Main implementation
2. `/home/zzz/project/o2o/tests/unit/test_user_features.py` - Unit tests
3. `/home/zzz/project/o2o/scripts/validate_user_metrics.py` - Validation script

## Dependencies

- `SQLAlchemy>=2.0.0` (already in requirements.txt)
- `pytest>=8.0.0` (for testing, already in requirements.txt)

## Notes

- Implementation follows SQLAlchemy best practices
- Uses type hints for better code clarity
- Handles edge cases (division by zero, NULL values, unknown distances)
- Optimized for batch processing with large datasets
- Ready for integration with Celery task queue (T034)