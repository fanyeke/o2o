"""Database models registration.

This file imports all models to register them with SQLAlchemy's metadata.
Import this file when you need to ensure all models are loaded.

Usage:
    from app.db.models import *  # noqa: F401, F403
    # or
    import app.db.models  # noqa: F401
"""

# Import all models to register them with Base.metadata
from app.domain.staging import CouponReceiptEvent, ConsumptionEvent  # noqa: F401
from app.domain.feature import MerchantMetrics, UserMetrics, CouponMetrics  # noqa: F401
from app.domain.raw.offline_train import OfflineTrain  # noqa: F401
from app.domain.raw.offline_test import OfflineTest  # noqa: F401
from app.domain.application import DecisionCase, Recommendation, ActionExecution, ApprovalLog  # noqa: F401