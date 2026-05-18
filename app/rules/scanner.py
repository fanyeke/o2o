"""Rule scanner for evaluating entity metrics against rule conditions.

This module provides functionality to:
- Scan entity metrics against rule conditions
- Identify entities that match rule criteria
- Create DecisionCases for matching entities

Task: T106, T107, T108
Phase: 5 - Rule Engine Configuration and Scanner
"""

import warnings
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.rules.yaml_loader import RuleConfig, RuleCondition
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.coupon_metrics import CouponMetrics
from app.domain.application.decision_case import DecisionCase


def evaluate_condition(condition: RuleCondition, field_value: Any) -> bool:
    """Evaluate a single condition against a field value.

    Args:
        condition: Rule condition with field, operator, and value
        field_value: Actual value from entity metrics

    Returns:
        True if condition is satisfied, False otherwise

    Note:
        If field_value is NULL/None, condition returns False
        (no match for NULL values)
    """
    # NULL values cannot match conditions
    if field_value is None:
        return False

    operator = condition.operator
    threshold = condition.value

    # Evaluate based on operator
    if operator == "gt":
        return field_value > threshold
    elif operator == "lt":
        return field_value < threshold
    elif operator == "gte":
        return field_value >= threshold
    elif operator == "lte":
        return field_value <= threshold
    elif operator == "eq":
        return field_value == threshold
    else:
        warnings.warn(
            f"Unknown operator '{operator}' in condition. Returning False.",
            UserWarning,
        )
        return False


def scan_merchant_rules(db: Session, rules: List[RuleConfig]) -> List[Dict[str, Any]]:
    """Scan merchant metrics against rule conditions.

    Args:
        db: Database session
        rules: List of merchant rules to evaluate

    Returns:
        List of match dictionaries containing:
        - merchant_id: ID of matching merchant
        - rule_id: ID of matching rule
        - rule_name: Name of matching rule
        - severity: Severity level of the rule
        - metrics_snapshot: Dictionary of merchant metrics at scan time

    Note:
        All conditions in a rule must be satisfied (AND logic).
        A merchant can match multiple rules, generating multiple matches.
    """
    matches = []

    # Query all merchant metrics
    merchant_metrics = db.query(MerchantMetrics).all()

    # Evaluate each merchant against each rule
    for merchant in merchant_metrics:
        for rule in rules:
            # Skip rules that don't apply to merchants
            if rule.entity_type != "merchant":
                continue

            # Evaluate all conditions (AND logic)
            all_conditions_met = True

            for condition in rule.conditions:
                # Get field value from merchant metrics
                field_value = getattr(merchant, condition.field, None)

                # Evaluate condition
                if not evaluate_condition(condition, field_value):
                    all_conditions_met = False
                    break  # No need to check remaining conditions

            # If all conditions are met, create a match
            if all_conditions_met:
                match = {
                    "merchant_id": merchant.merchant_id,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "severity": rule.severity,
                    "metrics_snapshot": {
                        "merchant_id": merchant.merchant_id,
                        "total_receipts_7d": merchant.total_receipts_7d,
                        "redeemed_count_7d": merchant.redeemed_count_7d,
                        "redeemed_rate_7d": merchant.redeemed_rate_7d,
                        "total_receipts_30d": merchant.total_receipts_30d,
                        "redeemed_count_30d": merchant.redeemed_count_30d,
                        "redeemed_rate_30d": merchant.redeemed_rate_30d,
                        "redeemed_rate_change": merchant.redeemed_rate_change,
                        "avg_discount_depth": merchant.avg_discount_depth,
                        "activity_health_score": merchant.activity_health_score,
                        "last_activity_date": str(merchant.last_activity_date) if merchant.last_activity_date else None,
                        "updated_at": str(merchant.updated_at) if merchant.updated_at else None,
                    }
                }
                matches.append(match)

    return matches


def create_decision_cases(
    db: Session,
    matches: List[Dict[str, Any]],
    dry_run: bool = False
) -> List[DecisionCase]:
    """Create DecisionCases from rule matches.

    Args:
        db: Database session
        matches: List of match dictionaries from rule scanning
        dry_run: If True, returns preview without persisting to database

    Returns:
        List of DecisionCase objects (persisted if dry_run=False)

    Note:
        In dry_run mode, cases are not persisted to database.
        This allows previewing the impact of rule scanning without
        creating actual decision cases.

        case_type is mapped to database constraint values:
        - merchant rules -> '商户异常'
        - coupon rules -> '券策略复核'
        - user rules -> '用户召回'
    """
    cases = []
    current_time = datetime.now()

    # Mapping from entity_type to database case_type values
    entity_to_case_type = {
        "merchant": "商户异常",
        "coupon": "券策略复核",
        "user": "用户召回",
    }

    for match in matches:
        # Determine entity_type from match fields
        if match.get("merchant_id"):
            entity_type = "merchant"
        elif match.get("coupon_id"):
            entity_type = "coupon"
        elif match.get("user_id"):
            entity_type = "user"
        else:
            # Default to merchant if no entity field found
            entity_type = "merchant"

        # Map entity_type to database case_type value
        case_type = entity_to_case_type.get(entity_type, "商户异常")

        # Create DecisionCase
        case = DecisionCase(
            case_type=case_type,
            severity_level=match["severity"],
            merchant_id=match.get("merchant_id"),
            coupon_id=match.get("coupon_id"),
            user_id=match.get("user_id"),
            trigger_rule_id=match["rule_id"],
            trigger_metrics_snapshot=match["metrics_snapshot"],
            status="pending",
            created_at=current_time,
            updated_at=current_time,
        )

        cases.append(case)

        # Persist to database if NOT dry run
        if not dry_run:
            db.add(case)

    # Commit if NOT dry run
    if not dry_run and cases:
        db.commit()

    return cases


def scan_all_rules(
    db: Session,
    rules: List[RuleConfig],
    dry_run: bool = False
) -> Dict[str, Any]:
    """Scan all entity types against all rules.

    Args:
        db: Database session
        rules: List of all rules to evaluate
        dry_run: If True, returns preview without persisting

    Returns:
        Dictionary containing:
        - merchant_matches: List of merchant matches
        - user_matches: List of user matches (placeholder for future)
        - coupon_matches: List of coupon matches (placeholder for future)
        - total_matches: Total count of matches
        - decision_cases: List of created DecisionCases

    Note:
        Currently only implements merchant scanning.
        User and coupon scanning will be implemented in future phases.
    """
    # Separate rules by entity type
    merchant_rules = [r for r in rules if r.entity_type == "merchant"]
    user_rules = [r for r in rules if r.entity_type == "user"]
    coupon_rules = [r for r in rules if r.entity_type == "coupon"]

    # Scan merchant metrics
    merchant_matches = scan_merchant_rules(db, merchant_rules)

    # Placeholder for user and coupon scanning (future implementation)
    user_matches = []
    coupon_matches = []

    # Create decision cases for all matches
    all_matches = merchant_matches + user_matches + coupon_matches
    decision_cases = create_decision_cases(db, all_matches, dry_run)

    return {
        "merchant_matches": merchant_matches,
        "user_matches": user_matches,
        "coupon_matches": coupon_matches,
        "total_matches": len(all_matches),
        "decision_cases": decision_cases,
        "dry_run": dry_run,
    }