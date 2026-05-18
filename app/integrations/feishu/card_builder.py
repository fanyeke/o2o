"""Feishu Card Builder for constructing approval cards.

M6 Milestone: Feishu Closed-loop Integration

This module provides utilities for building Feishu interactive cards
for approval workflow.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeishuCardBuilder:
    """Builder for Feishu interactive approval cards.

    Constructs card JSON structures that comply with Feishu Bot API format.
    Cards include:
    - Case summary and evidence
    - Risk alerts
    - Approve/Reject action buttons
    """

    def __init__(self):
        """Initialize the card builder."""
        pass

    def build_approval_card(
        self,
        case_data: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> dict[str, Any]:
        """Build an approval card for a decision case.

        Args:
            case_data: Decision case data including case_id, case_type, status
            recommendation: Recommendation data including evidence_list, risk_alerts,
                           suggested_actions, confidence_score

        Returns:
            Feishu card JSON structure
        """
        case_id = case_data.get("case_id", 0)
        case_type = case_data.get("case_type", "unknown")
        merchant_id = case_data.get("merchant_id", "unknown")
        merchant_name = case_data.get("merchant_name", merchant_id)

        summary = recommendation.get("summary", "")
        evidence_list = recommendation.get("evidence_list", [])
        risk_alerts = recommendation.get("risk_alerts")
        suggested_actions = recommendation.get("suggested_actions", [])
        confidence_score = recommendation.get("confidence_score", 0.0)

        # Build card structure
        card = {
            "card": {
                "config": {
                    "wide_screen_mode": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"审批请求 - {case_type}",
                    },
                    "template": self._get_severity_color(case_type),
                },
                "elements": self._build_elements(
                    case_id=case_id,
                    merchant_name=merchant_name,
                    summary=summary,
                    evidence_list=evidence_list,
                    risk_alerts=risk_alerts,
                    suggested_actions=suggested_actions,
                    confidence_score=confidence_score,
                ),
            }
        }

        return card

    def build_status_update_card(
        self,
        case_id: int,
        new_status: str,
        operator_name: str,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build a status update card after approval/rejection.

        Args:
            case_id: Decision case ID
            new_status: New case status (approved/rejected/executed)
            operator_name: Operator who performed the action
            comment: Optional comment

        Returns:
            Feishu card JSON structure
        """
        status_text = self._get_status_display(new_status)
        status_color = self._get_status_color(new_status)

        card = {
            "card": {
                "config": {
                    "wide_screen_mode": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"案例 {case_id} 已更新",
                    },
                    "template": status_color,
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**状态**: {status_text}",
                        },
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**操作人**: {operator_name}",
                        },
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                        },
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": comment or "无备注",
                            }
                        ]
                    },
                ],
            }
        }

        return card

    def _build_elements(
        self,
        case_id: int,
        merchant_name: str,
        summary: str,
        evidence_list: list[dict],
        risk_alerts: Optional[str],
        suggested_actions: list[dict],
        confidence_score: float,
    ) -> list[dict]:
        """Build card elements.

        Args:
            case_id: Decision case ID
            merchant_name: Merchant name
            summary: Summary text
            evidence_list: List of evidence items
            risk_alerts: Risk alert text
            suggested_actions: List of suggested actions
            confidence_score: Confidence score

        Returns:
            List of card elements
        """
        elements = []

        # Merchant info
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**商户**: {merchant_name}\n**案例ID**: {case_id}",
            },
        })

        # Summary
        if summary:
            # Truncate long summary
            display_summary = summary[:500] if len(summary) > 500 else summary
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**诊断摘要**: {display_summary}",
                },
            })

        # Evidence section
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "**证据列表**:",
            },
        })

        if evidence_list:
            for evidence in evidence_list:
                evidence_type = evidence.get("type", "metric")
                evidence_desc = evidence.get("description", "")
                # Truncate long description
                display_desc = evidence_desc[:200] if len(evidence_desc) > 200 else evidence_desc
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"- [{evidence_type}] {display_desc}",
                    },
                })
        else:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "- 无证据",
                },
            })

        # Risk alerts
        if risk_alerts:
            # Truncate long risk text
            display_risk = risk_alerts[:300] if len(risk_alerts) > 300 else risk_alerts
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**风险提示**: {display_risk}",
                },
            })

        # Suggested actions
        if suggested_actions:
            actions_text = "**建议动作**:\n"
            for action in suggested_actions:
                action_type = action.get("type") or action.get("action_type", "unknown")
                actions_text += f"- {action_type}\n"

            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": actions_text,
                },
            })

        # Confidence score
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**置信度**: {confidence_score:.2%}",
            },
        })

        # Divider
        elements.append({
            "tag": "hr",
        })

        # Action buttons
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "Approve",
                    },
                    "type": "primary",
                    "value": {
                        "case_id": case_id,
                        "action_type": "approve",
                        "operator_id": "",
                        "comment": "",
                    },
                },
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "Reject",
                    },
                    "type": "danger",
                    "value": {
                        "case_id": case_id,
                        "action_type": "reject",
                        "operator_id": "",
                        "comment": "",
                    },
                },
            ],
        })

        return elements

    def _get_severity_color(self, case_type: str) -> str:
        """Get card header color based on case type severity.

        Args:
            case_type: Case type string

        Returns:
            Feishu color template name
        """
        high_risk_types = ["fraud_detected", "high_refund_rate", "coupon_abuse"]
        medium_risk_types = ["low_redemption_rate", "unusual_pattern"]

        if case_type in high_risk_types:
            return "red"
        elif case_type in medium_risk_types:
            return "orange"
        else:
            return "blue"

    def _get_status_color(self, status: str) -> str:
        """Get card header color based on status.

        Args:
            status: Case status string

        Returns:
            Feishu color template name
        """
        if status in ["approved", "executed"]:
            return "green"
        elif status == "rejected":
            return "red"
        else:
            return "grey"

    def _get_status_display(self, status: str) -> str:
        """Get display text for status.

        Args:
            status: Case status string

        Returns:
            Human-readable status text
        """
        status_map = {
            "approved": "已批准",
            "rejected": "已拒绝",
            "executed": "已执行",
            "recommended": "待审批",
            "pending": "待处理",
        }
        return status_map.get(status, status)


def build_feishu_card_json(card: dict[str, Any]) -> str:
    """Convert card dict to JSON string for Feishu API.

    Args:
        card: Card dictionary structure

    Returns:
        JSON string representation
    """
    return json.dumps(card, ensure_ascii=False)