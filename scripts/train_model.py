#!/usr/bin/env python3
"""CLI script to train coupon redemption prediction model."""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.ml.train import CouponRedemptionPredictor


def main():
    """Main training script entry point."""
    parser = argparse.ArgumentParser(
        description="Train coupon redemption prediction model"
    )
    parser.add_argument(
        '--num-rounds',
        type=int,
        default=1000,
        help='Maximum number of boosting rounds (default: 1000)'
    )
    parser.add_argument(
        '--early-stopping-rounds',
        type=int,
        default=50,
        help='Early stopping patience (default: 50)'
    )
    parser.add_argument(
        '--verbose-eval',
        type=int,
        default=100,
        help='Print evaluation every N rounds (default: 100)'
    )
    parser.add_argument(
        '--model-name',
        type=str,
        default='redeem_predictor',
        help='Model filename (default: redeem_predictor)'
    )
    parser.add_argument(
        '--artifacts-dir',
        type=str,
        default='app/ml/artifacts',
        help='Directory to save trained models (default: app/ml/artifacts)'
    )
    parser.add_argument(
        '--num-leaves',
        type=int,
        default=31,
        help='LightGBM num_leaves parameter (default: 31)'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.05,
        help='LightGBM learning_rate parameter (default: 0.05)'
    )
    parser.add_argument(
        '--feature-fraction',
        type=float,
        default=0.8,
        help='LightGBM feature_fraction parameter (default: 0.8)'
    )

    args = parser.parse_args()

    # Create database session
    db: Session = SessionLocal()

    try:
        # Model parameters
        model_params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': args.num_leaves,
            'learning_rate': args.learning_rate,
            'feature_fraction': args.feature_fraction,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': 42
        }

        # Initialize predictor
        predictor = CouponRedemptionPredictor(
            db=db,
            model_params=model_params,
            artifacts_dir=args.artifacts_dir
        )

        print("=" * 80)
        print("Coupon Redemption Prediction Model Training")
        print("=" * 80)
        print(f"\nModel Parameters:")
        for key, value in model_params.items():
            print(f"  {key}: {value}")
        print(f"\nTraining Configuration:")
        print(f"  Max rounds: {args.num_rounds}")
        print(f"  Early stopping: {args.early_stopping_rounds}")
        print(f"  Verbose eval: {args.verbose_eval}")
        print(f"  Model name: {args.model_name}")
        print(f"  Artifacts dir: {args.artifacts_dir}")

        # Train full pipeline
        test_metrics, feature_importance = predictor.train_full_pipeline(
            num_rounds=args.num_rounds,
            early_stopping_rounds=args.early_stopping_rounds,
            verbose_eval=args.verbose_eval
        )

        print("\n" + "=" * 80)
        print("Training Complete!")
        print("=" * 80)
        print("\nTest Set Results:")
        print(f"  Grouped AUC: {test_metrics['grouped_auc']:.4f}")
        print(f"  Overall AUC: {test_metrics['overall_auc']:.4f}")
        print(f"  Samples: {test_metrics['num_samples']}")
        print(f"  Valid Groups: {test_metrics['num_valid_groups']}/{test_metrics['num_groups']}")

        print("\nTop 10 Feature Importance:")
        print(feature_importance.head(10).to_string(index=False))

        # Check baseline threshold
        baseline_threshold = 0.68
        if test_metrics['grouped_auc'] >= baseline_threshold:
            print(f"\n✓ SUCCESS: Model meets baseline threshold (AUC >= {baseline_threshold})")
            return 0
        else:
            print(f"\n✗ WARNING: Model below baseline threshold (AUC < {baseline_threshold})")
            print("  Consider tuning hyperparameters or adding more features")
            return 1

    except Exception as e:
        print(f"\n✗ ERROR: Training failed with error:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())