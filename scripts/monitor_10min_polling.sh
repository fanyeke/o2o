#!/bin/bash
# 每10分钟自动轮询监控Time-safe特征计算进度

echo "=== Time-safe特征计算监控（每10分钟轮询） ==="
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "目标: 1,011,990 receipts (2016-01-01 to 2016-06-15)"
echo ""

while true; do
    # 获取进度数据
    result=$(docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -t -c "
        SELECT
            COUNT(*) as count,
            MIN(as_of_date) as min_date,
            MAX(as_of_date) as max_date,
            COUNT(DISTINCT as_of_date) as days,
            ROUND(COUNT(*)::numeric / 1011990.0 * 100, 2) as pct
        FROM feature.receipt_training_features
    ")

    count=$(echo "$result" | awk '{print $1}')
    min_date=$(echo "$result" | awk '{print $2}')
    max_date=$(echo "$result" | awk '{print $3}')
    days=$(echo "$result" | awk '{print $4}')
    pct=$(echo "$result" | awk '{print $5}')

    # 获取进程状态
    process=$(ps aux | grep compute_time_safe_features | grep -v grep | grep 3428272)
    is_running=$(echo "$process" | wc -l)

    timestamp=$(date '+%H:%M:%S')

    echo "[$timestamp] 📊 Progress Report:"
    echo "  Receipts: $count / 1,011,990 ($pct%)"
    echo "  Dates: $min_date to $max_date ($days days processed)"
    echo "  Remaining: $((1011990 - count)) receipts"
    echo "  Process: $([ "$is_running" -gt 0 ] && echo "✓ Running" || echo "✗ Stopped")"
    echo ""

    # 检查是否完成
    if [ "$count" -ge 1010000 ]; then
        echo "🎉 ========================================"
        echo "🎉 Time-safe特征计算完成！"
        echo "🎉 ========================================"
        echo ""
        echo "Final statistics:"
        docker exec o2o-postgres-1 psql -U coupon_user -d coupon_agent -c "
            SELECT
                COUNT(*) as total_receipts,
                MIN(as_of_date) as start_date,
                MAX(as_of_date) as end_date,
                COUNT(DISTINCT as_of_date) as total_days,
                COUNT(*) FILTER (WHERE user_receipts_30d_before IS NOT NULL) / COUNT(*)::float as user_coverage,
                COUNT(*) FILTER (WHERE merchant_receipts_30d_before IS NOT NULL) / COUNT(*)::float as merchant_coverage
            FROM feature.receipt_training_features
        "
        echo ""
        echo "🎯 开始执行M1验收测试..."
        echo ""

        # 执行M1验收测试
        PYTHONPATH=/home/zzz/project/o2o venv/bin/python -m pytest tests/validation/test_time_leakage_audit.py -v

        echo ""
        echo "=== M1验收完成 ==="
        break
    fi

    # 等待10分钟
    echo "  Next check in 10 minutes..."
    echo ""
    sleep 600
done