"""Model evaluation with grouped AUC metric."""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score


class GroupedAUCEvaluator:
    """Calculate AUC grouped by coupon ID (Tianchi competition standard)."""

    def calculate_grouped_auc(
        self,
        predictions: np.ndarray,
        labels: np.ndarray,
        group_ids: np.ndarray
    ) -> float:
        """Calculate average AUC across groups.

        This metric groups predictions by coupon_id and calculates
        AUC for each group separately, then averages across all groups.
        This is the standard evaluation metric for Tianchi O2O competition.

        Args:
            predictions: Model predictions (probabilities)
            labels: True labels (0/1)
            group_ids: Group identifiers (coupon_id)

        Returns:
            Average AUC across all groups
        """
        unique_groups = np.unique(group_ids)
        group_aucs = []

        for group_id in unique_groups:
            # Get data for this group
            group_mask = group_ids == group_id
            group_preds = predictions[group_mask]
            group_labels = labels[group_mask]

            # Skip groups with only one class (no AUC can be calculated)
            if len(np.unique(group_labels)) < 2:
                continue

            # Calculate AUC for this group
            try:
                auc = roc_auc_score(group_labels, group_preds)
                group_aucs.append(auc)
            except ValueError:
                # Skip if AUC calculation fails
                continue

        if len(group_aucs) == 0:
            raise ValueError("No valid groups with both classes found")

        return np.mean(group_aucs)

    def calculate_overall_auc(
        self,
        predictions: np.ndarray,
        labels: np.ndarray
    ) -> float:
        """Calculate overall AUC (not grouped).

        Args:
            predictions: Model predictions (probabilities)
            labels: True labels (0/1)

        Returns:
            Overall AUC score
        """
        return roc_auc_score(labels, predictions)

    def evaluate_model(
        self,
        predictions: np.ndarray,
        labels: np.ndarray,
        group_ids: np.ndarray
    ) -> Dict[str, Any]:
        """Comprehensive model evaluation.

        Args:
            predictions: Model predictions (probabilities)
            labels: True labels (0/1)
            group_ids: Group identifiers (coupon_id)

        Returns:
            Dictionary with evaluation metrics
        """
        # Calculate grouped AUC (Tianchi standard)
        grouped_auc = self.calculate_grouped_auc(predictions, labels, group_ids)

        # Calculate overall AUC
        overall_auc = self.calculate_overall_auc(predictions, labels)

        # Additional statistics
        positive_rate = labels.mean()
        avg_prediction = predictions.mean()

        return {
            'grouped_auc': grouped_auc,
            'overall_auc': overall_auc,
            'positive_rate': positive_rate,
            'avg_prediction': avg_prediction,
            'num_samples': len(labels),
            'num_groups': len(np.unique(group_ids)),
            'num_valid_groups': len([
                g for g in np.unique(group_ids)
                if len(np.unique(labels[group_ids == g])) >= 2
            ])
        }

    def check_baseline_threshold(
        self,
        auc_score: float,
        threshold: float = 0.68
    ) -> bool:
        """Check if AUC meets baseline threshold.

        Tianchi competition baseline AUC is 0.68.

        Args:
            auc_score: AUC score to check
            threshold: Minimum required AUC (default: 0.68)

        Returns:
            True if AUC meets threshold

        Raises:
            ValueError: If AUC is below threshold
        """
        if auc_score < threshold:
            raise ValueError(
                f"AUC score {auc_score:.4f} is below baseline threshold "
                f"{threshold:.4f}"
            )
        return True

    def get_performance_level(self, auc_score: float) -> str:
        """Get performance level classification.

        Args:
            auc_score: AUC score

        Returns:
            Performance level string
        """
        if auc_score >= 0.80:
            return "Excellent"
        elif auc_score >= 0.75:
            return "Good"
        elif auc_score >= 0.68:
            return "Baseline"
        elif auc_score >= 0.60:
            return "Below Baseline"
        else:
            return "Poor"


class ModelEvaluator:
    """Comprehensive model evaluation with multiple metrics."""

    def __init__(self):
        """Initialize model evaluator."""
        self.grouped_auc_evaluator = GroupedAUCEvaluator()

    def evaluate_model(
        self,
        predictions: np.ndarray,
        labels: np.ndarray,
        group_ids: np.ndarray
    ) -> Dict[str, Any]:
        """Evaluate model predictions (alias for grouped_auc_evaluator).

        Args:
            predictions: Model predictions (probabilities)
            labels: True labels (0/1)
            group_ids: Group identifiers (coupon_id)

        Returns:
            Dictionary with evaluation metrics
        """
        return self.grouped_auc_evaluator.evaluate_model(
            predictions, labels, group_ids
        )

    def evaluate_predictions(
        self,
        df: pd.DataFrame,
        prediction_column: str = 'predicted_probability',
        label_column: str = 'is_redeemed',
        group_column: str = 'coupon_id'
    ) -> Dict[str, Any]:
        """Evaluate predictions in dataframe format.

        Args:
            df: DataFrame with predictions and labels
            prediction_column: Column name for predictions
            label_column: Column name for labels
            group_column: Column name for group IDs

        Returns:
            Dictionary with evaluation metrics
        """
        predictions = df[prediction_column].values
        labels = df[label_column].values.astype(int)
        group_ids = df[group_column].values

        return self.grouped_auc_evaluator.evaluate_model(
            predictions, labels, group_ids
        )

    def compare_models(
        self,
        results: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """Compare multiple model evaluation results.

        Args:
            results: List of evaluation result dictionaries

        Returns:
            DataFrame with comparison table
        """
        comparison_df = pd.DataFrame(results)
        comparison_df['performance_level'] = comparison_df['grouped_auc'].apply(
            self.grouped_auc_evaluator.get_performance_level
        )
        return comparison_df.sort_values('grouped_auc', ascending=False)