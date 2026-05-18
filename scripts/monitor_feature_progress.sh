#!/bin/bash
# Time-safe特征计算进度监控脚本

echo "=== Time-safe特征计算进度监控 ==="
echo ""

while true; do
    result=$(docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -t -c "
        SELECT
            COUNT(*) as count,
            MIN(as_of_date) as min_date,
            MAX(as_of_date) as max_date,
            COUNT(DISTINCT user_id) as users,
            COUNT(DISTINCT merchant_id) as merchants,
            COUNT(DISTINCT coupon_id) as coupons
        FROM feature.receipt_training_features
    ")

    count=$(echo "$result" | awk '{print $1}')
    min_date=$(echo "$result" | awk '{print $2}')
    max_date=$(echo "$result" | awk '{print $3}')
    users=$(echo "$result" | awk '{print $4}')
    merchants=$(echo "$result" | awk '{print $5}')
    coupons=$(echo "$result" | awk '{print $6}')

    progress_pct=$(awk "BEGIN {printf \"%.2f\", ($count / 1011990) * 100}")

    echo "[$(date '+%H:%M:%S')] Progress: $count / 1,011,990 ($progress_pct%)"
    echo "  Date range: $min_date to $max_date"
    echo "  Unique: $users users, $merchants merchants, $coupons coupons"
    echo ""

    if [ "$count" -ge 1010000 ]; then
        echo "✓ Time-safe features computation completed!"
        echo "Final count: $count receipts"
        break
    fi

    sleep 60
done

echo ""
echo "=== Final statistics ==="
docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
    SELECT
        COUNT(*) as total_receipts,
        MIN(as_of_date) as min_date,
        MAX(as_of_date) as max_date,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT merchant_id) as unique_merchants,
        COUNT(DISTINCT coupon_id) as unique_coupons
    FROM feature.receipt_training_features
"