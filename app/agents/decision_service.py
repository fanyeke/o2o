"""Agent Decision Service - Core decision-making logic.

This service orchestrates the agent decision flow:
1. Retrieve data via Tools
2. Build prompt with context
3. Call DeepSeek LLM with JSON Mode
4. Parse structured recommendation
5. Persist recommendation to database
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.integrations.llm.deepseek_client import DeepSeekClient
from app.agents.tools import execute_tool, AVAILABLE_TOOLS
from app.agents.prompts.decision_prompt import build_decision_prompt

logger = logging.getLogger(__name__)


class AgentDecisionService:
    """Service for generating agent decisions."""

    def __init__(self, db: Session):
        """Initialize decision service.

        Args:
            db: Database session
        """
        self.db = db
        self.llm_client = DeepSeekClient()

    def generate_recommendation(self, case_id: int) -> Optional[Recommendation]:
        """Generate recommendation for a decision case.

        Args:
            case_id: DecisionCase ID

        Returns:
            Recommendation instance if successful, None if failed
        """
        logger.info(f"Generating recommendation for case {case_id}")

        # 1. Retrieve decision case
        case = self.db.query(DecisionCase).filter(DecisionCase.id == case_id).first()

        if not case:
            logger.error(f"DecisionCase {case_id} not found")
            return None

        if case.status != "pending":
            logger.warning(
                f"DecisionCase {case_id} status is {case.status}, "
                f"expected 'pending'"
            )
            return None

        # 2. Execute tools to gather data
        tool_results = self._execute_tools(case)
        tool_trace = self._build_tool_trace(tool_results)

        # 3. Build prompt with context
        prompt = build_decision_prompt(case, tool_results)

        # 4. Call DeepSeek LLM with retry
        try:
            llm_response, tokens_used, latency = self.llm_client.generate_json_with_retry(
                prompt=prompt,
                max_retries=3,
                max_tokens=2000,
                temperature=0.7,
            )

            logger.info(
                f"LLM response received: tokens={tokens_used}, latency={latency:.2f}s"
            )

        except Exception as e:
            logger.error(f"LLM call failed after retries: {e}")

            # Update case status to 'failed'
            case.status = "failed"
            case.updated_at = datetime.now()
            self.db.commit()

            return None

        # 5. Parse recommendation
        try:
            parsed_recommendation = parse_recommendation(llm_response)
        except ValueError as e:
            logger.error(f"Failed to parse recommendation: {e}")
            logger.error(f"LLM response: {llm_response}")

            # Update case status to 'failed'
            case.status = "failed"
            case.updated_at = datetime.now()
            self.db.commit()

            return None

        # 6. Persist recommendation
        recommendation = Recommendation(
            case_id=case_id,
            summary=parsed_recommendation["summary"],
            evidence_list=parsed_recommendation["evidence_list"],
            suggested_actions=parsed_recommendation["suggested_actions"],
            risk_alerts=parsed_recommendation.get("risk_alerts"),
            confidence_score=parsed_recommendation["confidence_score"],
            requires_approval=parsed_recommendation["requires_approval"],
            tool_trace=tool_trace,
            llm_raw_output=str(llm_response),
            llm_tokens_used=tokens_used,
            created_at=datetime.now(),
        )

        self.db.add(recommendation)

        # 7. Update case status
        case.status = "recommended"
        case.updated_at = datetime.now()

        self.db.commit()

        logger.info(
            f"Recommendation generated successfully for case {case_id}, "
            f"confidence={recommendation.confidence_score}, "
            f"requires_approval={recommendation.requires_approval}"
        )

        return recommendation

    def _execute_tools(self, case: DecisionCase) -> Dict[str, Any]:
        """Execute tools to gather data for the case.

        Args:
            case: DecisionCase instance

        Returns:
            Dictionary of tool execution results
        """
        logger.info(f"Executing tools for case {case.id}")

        results = {}

        # Always get merchant metrics if merchant_id is present
        if case.merchant_id:
            try:
                merchant_metrics = execute_tool(
                    self.db, "get_merchant_metrics", merchant_id=case.merchant_id
                )
                results["merchant_metrics"] = merchant_metrics

                # Also get coupon conversion data
                coupon_conversion = execute_tool(
                    self.db, "get_coupon_conversion", merchant_id=case.merchant_id
                )
                results["coupon_conversion"] = coupon_conversion

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")

        # Get user metrics if user_id is present
        if case.user_id:
            try:
                user_metrics = execute_tool(
                    self.db, "get_user_metrics", user_id=case.user_id
                )
                results["user_metrics"] = user_metrics

                # Get recent receipts for this user
                recent_receipts = execute_tool(
                    self.db, "get_recent_receipts", user_id=case.user_id, limit=10
                )
                results["recent_receipts"] = recent_receipts

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")

        logger.info(f"Executed {len(results)} tools for case {case.id}")

        return results

    def _build_tool_trace(self, tool_results: Dict[str, Any]) -> list:
        """Build tool trace for audit trail.

        Args:
            tool_results: Dictionary of tool execution results

        Returns:
            List of tool call records
        """
        trace = []

        for tool_name, result in tool_results.items():
            tool_info = AVAILABLE_TOOLS.get(tool_name, {})
            trace.append({
                "tool_name": tool_name,
                "description": tool_info.get("description", ""),
                "timestamp": datetime.now().isoformat(),
                "result_summary": f"Retrieved {tool_name} data"
                    if result else "No data found",
            })

        return trace


def parse_recommendation(llm_output: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate LLM output as recommendation.

    Args:
        llm_output: Dictionary from LLM JSON response

    Returns:
        Validated recommendation dictionary

    Raises:
        ValueError: If output is invalid or missing required fields
    """
    # Check required fields
    required_fields = [
        "summary",
        "evidence_list",
        "suggested_actions",
        "confidence_score",
        "requires_approval",
    ]

    for field in required_fields:
        if field not in llm_output:
            raise ValueError(f"Missing required field: {field}")

    # Validate evidence list
    evidence_list = llm_output["evidence_list"]

    if not isinstance(evidence_list, list):
        raise ValueError("evidence_list must be a list")

    if len(evidence_list) < 3:
        raise ValueError(
            f"At least 3 evidence items required, got {len(evidence_list)}"
        )

    # Validate each evidence item
    for evidence in evidence_list:
        if not isinstance(evidence, dict):
            raise ValueError("Each evidence item must be a dictionary")

        if "type" not in evidence or "description" not in evidence:
            raise ValueError(
                "Each evidence item must have 'type' and 'description' fields"
            )

    # Validate suggested actions
    suggested_actions = llm_output["suggested_actions"]

    if not isinstance(suggested_actions, list):
        raise ValueError("suggested_actions must be a list")

    for action in suggested_actions:
        if not isinstance(action, dict):
            raise ValueError("Each action must be a dictionary")

        if "action_type" not in action or "params" not in action:
            raise ValueError(
                "Each action must have 'action_type' and 'params' fields"
            )

        # Validate params is a dict
        if not isinstance(action.get("params"), dict):
            raise ValueError("params must be a dictionary")

    # Validate confidence score
    confidence_score = llm_output["confidence_score"]

    if not isinstance(confidence_score, (int, float)):
        raise ValueError("confidence_score must be a number")

    if not 0 <= confidence_score <= 1:
        raise ValueError(
            f"confidence_score must be between 0 and 1, got {confidence_score}"
        )

    # Validate requires_approval
    requires_approval = llm_output["requires_approval"]

    if not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be a boolean")

    # Return validated recommendation
    return {
        "summary": str(llm_output["summary"]),
        "evidence_list": evidence_list,
        "suggested_actions": suggested_actions,
        "risk_alerts": str(llm_output.get("risk_alerts", "")),
        "confidence_score": float(confidence_score),
        "requires_approval": requires_approval,
    }


# Convenience function for Celery task
def generate_recommendation(db: Session, case_id: int) -> Optional[Recommendation]:
    """Generate recommendation for a decision case.

    Args:
        db: Database session
        case_id: DecisionCase ID

    Returns:
        Recommendation instance if successful, None if failed
    """
    service = AgentDecisionService(db)
    return service.generate_recommendation(case_id)