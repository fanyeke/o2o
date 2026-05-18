"""LightGBM model training for coupon redemption prediction."""

from datetime import date
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
from pathlib import Path
from sqlalchemy.orm import Session

from app.ml.train.feature_extractor import FeatureExtractor
from app.ml.train.time_split import TimeSplitValidator, create_tianchi_split
from app.ml.train.evaluate_model import ModelEvaluator


class CouponRedemptionPredictor:
    """LightGBM-based coupon redemption prediction model."""

    def __init__(
        self,
        db: Session,
        model_params: Optional[Dict[str, Any]] = None,
        artifacts_dir: str = "app/ml/artifacts"
    ):
        """Initialize predictor.

        Args:
            db: SQLAlchemy session
            model_params: LightGBM parameters (optional)
            artifacts_dir: Directory to save trained models
        """
        self.db = db
        self.feature_extractor = FeatureExtractor(db)
        self.time_split = create_tianchi_split()
        self.evaluator = ModelEvaluator()
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Default LightGBM parameters
        self.model_params = model_params or {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': 42
        }

        self.model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = []
        self.best_iteration: int = 0

    def prepare_data(
        self,
        train_start: Optional[date] = None,
        train_end: Optional[date] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Prepare train/val/test datasets.

        Args:
            train_start: Override default training start date
            train_end: Override default training end date

        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        # Use Tianchi competition date range if not specified
        if train_start is None:
            train_start = self.time_split.train_start
        if train_end is None:
            train_end = self.time_split.test_end

        # Extract features from database
        print(f"Extracting features from {train_start} to {train_end}...")
        df = self.feature_extractor.extract_training_features(
            start_date=train_start,
            end_date=train_end
        )

        if df.empty:
            raise ValueError("No data extracted from database")

        print(f"Extracted {len(df)} samples")

        # Split by time
        train_df, val_df, test_df = self.time_split.split(df)

        # Validate splits
        self.time_split.validate_split(train_df, val_df, test_df)

        # Print split summary
        summary = self.time_split.get_split_summary(train_df, val_df, test_df)
        print("\nData split summary:")
        for split_name, stats in summary.items():
            print(f"  {split_name}: {stats['samples']} samples, "
                  f"{stats['positive_rate']:.2%} positive rate")

        return train_df, val_df, test_df

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        num_rounds: int = 1000,
        early_stopping_rounds: int = 50,
        verbose_eval: int = 100
    ) -> Dict[str, Any]:
        """Train LightGBM model.

        Args:
            train_df: Training dataframe
            val_df: Validation dataframe
            num_rounds: Maximum number of boosting rounds
            early_stopping_rounds: Early stopping patience
            verbose_eval: Print evaluation every N rounds

        Returns:
            Training metrics dictionary
        """
        # Get feature names
        self.feature_names = self.feature_extractor.get_feature_names()

        # Prepare data
        X_train = train_df[self.feature_names].values
        y_train = train_df['is_redeemed'].values.astype(int)
        train_groups = train_df['coupon_id'].values

        X_val = val_df[self.feature_names].values
        y_val = val_df['is_redeemed'].values.astype(int)
        val_groups = val_df['coupon_id'].values

        # Create LightGBM datasets
        train_data = lgb.Dataset(
            X_train,
            label=y_train,
            feature_name=self.feature_names
        )
        val_data = lgb.Dataset(
            X_val,
            label=y_val,
            feature_name=self.feature_names,
            reference=train_data
        )

        # Train model
        print("\nTraining LightGBM model...")
        self.model = lgb.train(
            self.model_params,
            train_data,
            num_boost_round=num_rounds,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'valid'],
            callbacks=[
                lgb.early_stopping(stopping_rounds=early_stopping_rounds),
                lgb.log_evaluation(period=verbose_eval)
            ]
        )

        self.best_iteration = self.model.best_iteration

        # Evaluate on validation set
        val_predictions = self.model.predict(X_val, num_iteration=self.best_iteration)
        val_metrics = self.evaluator.evaluate_model(
            val_predictions, y_val, val_groups
        )

        print(f"\nValidation metrics:")
        print(f"  Grouped AUC: {val_metrics['grouped_auc']:.4f}")
        print(f"  Overall AUC: {val_metrics['overall_auc']:.4f}")
        print(f"  Performance: {self.evaluator.grouped_auc_evaluator.get_performance_level(val_metrics['grouped_auc'])}")

        return val_metrics

    def evaluate_on_test(
        self,
        test_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Evaluate model on test set.

        Args:
            test_df: Test dataframe

        Returns:
            Test metrics dictionary
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        X_test = test_df[self.feature_names].values
        y_test = test_df['is_redeemed'].values.astype(int)
        test_groups = test_df['coupon_id'].values

        predictions = self.model.predict(X_test, num_iteration=self.best_iteration)
        test_metrics = self.evaluator.evaluate_model(
            predictions, y_test, test_groups
        )

        print(f"\nTest metrics:")
        print(f"  Grouped AUC: {test_metrics['grouped_auc']:.4f}")
        print(f"  Overall AUC: {test_metrics['overall_auc']:.4f}")
        print(f"  Performance: {self.evaluator.grouped_auc_evaluator.get_performance_level(test_metrics['grouped_auc'])}")

        # Check baseline threshold
        try:
            self.evaluator.grouped_auc_evaluator.check_baseline_threshold(
                test_metrics['grouped_auc']
            )
            print(f"  ✓ AUC meets baseline threshold (>= 0.68)")
        except ValueError as e:
            print(f"  ✗ Warning: {e}")

        return test_metrics

    def save_model(
        self,
        model_name: str = "redeem_predictor",
        include_metrics: bool = True,
        test_metrics: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Save trained model to disk.

        Args:
            model_name: Model filename (without extension)
            include_metrics: Include evaluation metrics in saved file
            test_metrics: Test set metrics to save

        Returns:
            Path to saved model file
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        model_path = self.artifacts_dir / f"{model_name}.joblib"

        save_dict = {
            'model': self.model,
            'feature_names': self.feature_names,
            'best_iteration': self.best_iteration,
            'model_params': self.model_params,
            'metadata': {
                'model_version': 'v1.0.0',
                'feature_version': 'v1_time_safe',
                'train_date_range': {
                    'start': str(self.time_split.train_start),
                    'end': str(self.time_split.train_end)
                }
            }
        }

        if include_metrics and test_metrics:
            save_dict['metadata']['metrics'] = test_metrics

        joblib.dump(save_dict, model_path)
        print(f"\nModel saved to: {model_path}")

        return model_path

    @classmethod
    def load_model(
        cls,
        model_path: str,
        db: Optional[Session] = None
    ) -> 'CouponRedemptionPredictor':
        """Load trained model from disk.

        Args:
            model_path: Path to saved model file
            db: SQLAlchemy session (optional, for inference)

        Returns:
            Loaded CouponRedemptionPredictor instance
        """
        model_path = Path(model_path)
        loaded_dict = joblib.load(model_path)

        # Create instance without __init__
        instance = cls.__new__(cls)
        instance.db = db
        instance.model = loaded_dict['model']
        instance.feature_names = loaded_dict['feature_names']
        instance.best_iteration = loaded_dict['best_iteration']
        instance.model_params = loaded_dict['model_params']
        instance.feature_extractor = FeatureExtractor(db) if db else None
        instance.time_split = create_tianchi_split()
        instance.evaluator = ModelEvaluator()
        instance.artifacts_dir = model_path.parent

        return instance

    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> pd.DataFrame:
        """Get feature importance from trained model.

        Args:
            importance_type: 'gain', 'split', or 'gain'

        Returns:
            DataFrame with feature importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        importance = self.model.feature_importance(importance_type=importance_type)
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return feature_importance

    def train_full_pipeline(
        self,
        num_rounds: int = 1000,
        early_stopping_rounds: int = 50,
        verbose_eval: int = 100
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Execute full training pipeline: prepare, train, evaluate, save.

        Args:
            num_rounds: Maximum boosting rounds
            early_stopping_rounds: Early stopping patience
            verbose_eval: Print evaluation every N rounds

        Returns:
            Tuple of (test_metrics, feature_importance)
        """
        # Prepare data
        train_df, val_df, test_df = self.prepare_data()

        # Train model
        val_metrics = self.train(
            train_df,
            val_df,
            num_rounds=num_rounds,
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=verbose_eval
        )

        # Evaluate on test
        test_metrics = self.evaluate_on_test(test_df)

        # Get feature importance
        feature_importance = self.get_feature_importance()

        # Save model
        self.save_model(test_metrics=test_metrics)

        return test_metrics, feature_importance