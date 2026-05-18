"""Feishu integration package.

M6 Milestone: Feishu Closed-loop Integration

Modules:
- signature_validator: Webhook signature validation with fail-closed behavior
- card_builder: Feishu interactive card construction
- message_client: Async client for card sending and updates with retry

Usage:
    from app.integrations.feishu import (
        FeishuSignatureValidator,
        FeishuCardBuilder,
        FeishuMessageClient,
    )
"""

from app.integrations.feishu.signature_validator import (
    FeishuSignatureValidator,
    create_feishu_validator_dependency,
)
from app.integrations.feishu.card_builder import (
    FeishuCardBuilder,
    build_feishu_card_json,
)
from app.integrations.feishu.message_client import (
    FeishuMessageClient,
    create_message_client_from_config,
)

__all__ = [
    "FeishuSignatureValidator",
    "create_feishu_validator_dependency",
    "FeishuCardBuilder",
    "build_feishu_card_json",
    "FeishuMessageClient",
    "create_message_client_from_config",
]