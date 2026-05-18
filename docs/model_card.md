# Model Card: Coupon Redemption Predictor

## Model Details

- **Model Name**: Coupon Redemption Predictor (redeem_predictor.joblib)
- **Model Type**: LightGBM Gradient Boosting Classifier
- **Version**: v1.0.0
- **Feature Version**: v1_time_safe
- **Training Date**: 2026-05-18
- **Developed by**: O2O Coupon Decision Agent Team

### Model Architecture
- **Algorithm**: LightGBM (GBDT boosting)
- **Objective**: Binary classification (coupon redemption)
- **Metric**: AUC (Area Under ROC Curve)
- **Hyperparameters**:
  - num_leaves: 31
  - learning_rate: 0.05
  - feature_fraction: 0.8
  - bagging_fraction: 0.8
  - bagging_freq: 5
  - early_stopping_rounds: 50

## Intended Use

### Primary Use Cases
1. **Coupon Distribution Optimization**: Predict which users are most likely to redeem coupons
2. **Targeted Marketing**: Identify high-probability users for personalized coupon offers
3. **Risk Assessment**: Flag low-probability distributions for operational review

### Out-of-Scope Uses
- This model should NOT be used for:
  - Financial credit decisions
  - User discrimination or unfair treatment
  - Predictions outside the Tianchi O2O dataset context

### Target Users
- Marketing operations teams
- Coupon distribution managers
- Business analysts

## Training Data

### Data Source
- Tianchi O2O Coupon Dataset (offline_train.csv)
- Date Range: 2016-01-01 to 2016-05-31
- Records: ~1.05M coupon receipt events

### Data Split
- **Training Set**: 2016-01-01 to 2016-04-30 (~80%)
- **Validation Set**: 2016-05-01 to 2016-05-31 (~10%)
- **Test Set**: 2016-06-01 to 2016-06-30 (~10%)

### Feature Engineering
- **Time-Safe Features**: All historical features computed using data BEFORE each receipt's date_received
- **Feature Count**: 16 features
- **Feature Categories**:
  - User historical metrics (30-day window)
  - Merchant historical metrics (7-day and 30-day windows)
  - Coupon historical metrics
  - Static features (discount, distance)
  - Time features (day of week, month, day of month)

### Key Features
| Feature | Description |
|---------|-------------|
| user_redeemed_rate_30d_before | User's 30-day redemption rate |
| merchant_redeemed_rate_30d_before | Merchant's 30-day redemption rate |
| coupon_redeemed_rate_before | Coupon's historical redemption rate |
| discount_value | Discount value (ratio or percentage) |
| distance | User-merchant distance |

## Evaluation Metrics

### Primary Metrics
- **Grouped AUC**: Average AUC per coupon_id (Tianchi competition standard)
- **Overall AUC**: Global AUC across all predictions
- **Baseline Threshold**: >= 0.68 (Tianchi competition baseline)

### Calibration Metrics
- **Expected Calibration Error (ECE)**: <= 0.05 required
- Model probabilities should match actual redemption rates

### Lift Metrics
- **Top 10% Lift**: >= 2x (model identifies high-probability users)
- **Top 20% Lift**: >= 1.5x

### Performance Metrics
- **Train-Test AUC Gap**: <= 0.08 (overfitting detection)
- **Prediction Latency P95**: <= 200ms per prediction

### Expected Performance
| Metric | Target | Actual (Post-Training) |
|--------|--------|------------------------|
| Grouped AUC | >= 0.68 | [Computed after training] |
| Overall AUC | >= 0.65 | [Computed after training] |
| ECE | <= 0.05 | [Computed after training] |
| Top 10% Lift | >= 2x | [Computed after training] |

## Ethical Considerations

### Fairness
- Model does not use demographic features (age, gender, location)
- Predictions based on behavioral history only
- Cold-start users receive neutral predictions

### Privacy
- User IDs are anonymized
- No personal identifying information in features
- Model trained on anonymized transaction data

### Bias Considerations
- **Cold Start Bias**: New users/merchants have limited historical data
- **Temporal Bias**: Model trained on 2016 data, may not generalize to different time periods
- **Merchant Bias**: Popular merchants have more reliable statistics

### Mitigation Strategies
- Use default values for cold-start cases (rate = 0)
- Monitor prediction distribution for anomalies
- Retrain model periodically with fresh data

## Limitations

### Known Limitations
1. **Time Period**: Model trained on 2016 data, may not reflect current consumer behavior
2. **Geographic Scope**: Tianchi dataset covers specific Chinese cities
3. **Merchant Coverage**: Only merchants with coupon activity
4. **Feature Coverage**: Cold-start users/merchants have limited accuracy

### Recommendations
- Retrain quarterly with latest data
- Monitor feature distributions for drift
- Validate predictions against actual redemption rates

## Deployment

### Model File
- Path: `app/ml/artifacts/redeem_predictor.joblib`
- Format: Joblib serialized LightGBM Booster
- Size: ~50MB (depends on training)

### Dependencies
- LightGBM >= 4.0
- NumPy >= 1.20
- Joblib >= 1.0
- SQLAlchemy (for feature extraction)

### API Integration
- Endpoint: `/api/v1/predict`
- Method: POST
- Input: Receipt event with user/merchant/coupon IDs
- Output: Redemption probability (0.0-1.0)

### Monitoring Requirements
- Track prediction latency
- Monitor prediction distribution
- Log feature values for drift detection
- Track actual redemption rates for model validation

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-05-18 | Initial time-safe feature model |

## References

- Tianchi O2O Coupon Usage Prediction Competition
- LightGBM Documentation: https://lightgbm.readthedocs.io/
- Model Cards for Model Reporting (Mitchell et al., 2019)