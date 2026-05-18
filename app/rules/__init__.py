"""Rule engine module for scanning entity metrics and triggering decision cases.

This module provides:
- yaml_loader: Load rule configurations from YAML files
- scanner: Execute rules and create decision cases for matching entities

Phase: 5 - Rule Engine Configuration and Scanner
"""

from app.rules.yaml_loader import load_rules, RuleConfig, RuleCondition
from app.rules.scanner import (
    scan_merchant_rules,
    create_decision_cases,
    scan_all_rules,
    evaluate_condition,
)

__all__ = [
    "load_rules",
    "RuleConfig",
    "RuleCondition",
    "scan_merchant_rules",
    "create_decision_cases",
    "scan_all_rules",
    "evaluate_condition",
]