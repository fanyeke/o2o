"""Time-based data splitting for model training and validation."""

from datetime import date, timedelta
from typing import Tuple
import pandas as pd


class TimeSplitValidator:
    """Time-based data splitter to prevent data leakage."""

    def __init__(
        self,
        train_start: date,
        train_end: date,
        val_start: date,
        val_end: date,
        test_start: date,
        test_end: date
    ):
        """Initialize time split validator.

        Args:
            train_start: Training set start date
            train_end: Training set end date
            val_start: Validation set start date
            val_end: Validation set end date
            test_start: Test set start date
            test_end: Test set end date
        """
        self.train_start = train_start
        self.train_end = train_end
        self.val_start = val_start
        self.val_end = val_end
        self.test_start = test_start
        self.test_end = test_end

    def split(
        self,
        df: pd.DataFrame,
        date_column: str = 'date_received'
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split dataframe into train/val/test sets by date.

        Args:
            df: Input dataframe with date column
            date_column: Name of the date column

        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        df[date_column] = pd.to_datetime(df[date_column])

        train_mask = (df[date_column] >= pd.Timestamp(self.train_start)) & \
                     (df[date_column] <= pd.Timestamp(self.train_end))
        val_mask = (df[date_column] >= pd.Timestamp(self.val_start)) & \
                   (df[date_column] <= pd.Timestamp(self.val_end))
        test_mask = (df[date_column] >= pd.Timestamp(self.test_start)) & \
                    (df[date_column] <= pd.Timestamp(self.test_end))

        train_df = df[train_mask].copy()
        val_df = df[val_mask].copy()
        test_df = df[test_mask].copy()

        return train_df, val_df, test_df

    def validate_split(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> bool:
        """Validate that splits are non-empty and properly ordered.

        Args:
            train_df: Training dataframe
            val_df: Validation dataframe
            test_df: Test dataframe

        Returns:
            True if splits are valid

        Raises:
            ValueError: If splits are invalid
        """
        if train_df.empty:
            raise ValueError("Training set is empty")
        if val_df.empty:
            raise ValueError("Validation set is empty")
        if test_df.empty:
            raise ValueError("Test set is empty")

        # Check date ordering
        if self.train_end >= self.val_start:
            raise ValueError(
                f"Training end date {self.train_end} must be before "
                f"validation start date {self.val_start}"
            )
        if self.val_end >= self.test_start:
            raise ValueError(
                f"Validation end date {self.val_end} must be before "
                f"test start date {self.test_start}"
            )

        return True

    def get_split_summary(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> dict:
        """Get summary statistics of data splits.

        Args:
            train_df: Training dataframe
            val_df: Validation dataframe
            test_df: Test dataframe

        Returns:
            Dictionary with split statistics
        """
        return {
            'train': {
                'start_date': self.train_start,
                'end_date': self.train_end,
                'samples': len(train_df),
                'positive_rate': train_df['is_redeemed'].mean() if 'is_redeemed' in train_df.columns else None
            },
            'validation': {
                'start_date': self.val_start,
                'end_date': self.val_end,
                'samples': len(val_df),
                'positive_rate': val_df['is_redeemed'].mean() if 'is_redeemed' in val_df.columns else None
            },
            'test': {
                'start_date': self.test_start,
                'end_date': self.test_end,
                'samples': len(test_df),
                'positive_rate': test_df['is_redeemed'].mean() if 'is_redeemed' in test_df.columns else None
            }
        }


def create_tianchi_split() -> TimeSplitValidator:
    """Create time split validator with Tianchi competition dates.

    Tianchi O2O dataset date ranges:
    - Training: 2016-01-01 to 2016-04-30
    - Validation: 2016-05-01 to 2016-05-31
    - Test: 2016-06-01 to 2016-06-30

    Returns:
        TimeSplitValidator instance with Tianchi dates
    """
    return TimeSplitValidator(
        train_start=date(2016, 1, 1),
        train_end=date(2016, 4, 30),
        val_start=date(2016, 5, 1),
        val_end=date(2016, 5, 31),
        test_start=date(2016, 6, 1),
        test_end=date(2016, 6, 30)
    )