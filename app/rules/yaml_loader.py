"""YAML rule loader for the rule engine.

This module provides functionality to load rule configurations from YAML files.
Rules define conditions for triggering decision cases based on entity metrics.

Task: T101, T105
Phase: 5 - Rule Engine Configuration and Scanner
"""

import warnings
from pathlib import Path
from typing import List, Optional, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class RuleCondition(BaseModel):
    """A single condition in a rule.

    Each condition specifies:
    - field: The metric field to evaluate (e.g., 'redeemed_rate_change')
    - operator: Comparison operator (gt, lt, gte, lte, eq)
    - value: The threshold value to compare against
    """

    field: str = Field(..., description="Metric field name to evaluate")
    operator: Literal["gt", "lt", "gte", "lte", "eq"] = Field(
        ..., description="Comparison operator"
    )
    value: float = Field(..., description="Threshold value")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """Validate that operator is one of the supported values."""
        valid_operators = {"gt", "lt", "gte", "lte", "eq"}
        if v not in valid_operators:
            raise ValueError(
                f"Invalid operator '{v}'. Must be one of: {valid_operators}"
            )
        return v


class RuleConfig(BaseModel):
    """A complete rule configuration.

    Each rule specifies:
    - id: Unique identifier for the rule
    - name: Human-readable name
    - description: Detailed description of the rule's purpose
    - entity_type: Type of entity this rule applies to (merchant, user, coupon)
    - conditions: List of conditions that must all be satisfied (AND logic)
    - severity: Severity level of the decision case (high, medium, low)
    """

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field(..., description="Rule description")
    entity_type: Literal["merchant", "user", "coupon"] = Field(
        ..., description="Entity type this rule applies to"
    )
    conditions: List[RuleCondition] = Field(
        ..., min_length=1, description="List of conditions (all must be satisfied)"
    )
    severity: Literal["high", "medium", "low"] = Field(
        default="medium", description="Severity level of the decision case"
    )

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate that entity_type is one of the supported values."""
        valid_entity_types = {"merchant", "user", "coupon"}
        if v not in valid_entity_types:
            raise ValueError(
                f"Invalid entity_type '{v}'. Must be one of: {valid_entity_types}"
            )
        return v


def load_rules(rules_dir: Path, rule_ids: Optional[List[str]] = None) -> List[RuleConfig]:
    """Load rule configurations from YAML files in a directory.

    Args:
        rules_dir: Path to directory containing YAML rule files
        rule_ids: Optional list of specific rule IDs to load.
                  If None, loads all rules from the directory.

    Returns:
        List of RuleConfig objects

    Raises:
        FileNotFoundError: If rules_dir does not exist

    Note:
        Invalid YAML files or rule configurations are skipped with a warning.
        This allows the system to continue functioning even with some
        malformed rule files.
    """
    if not rules_dir.exists():
        raise FileNotFoundError(f"Rules directory not found: {rules_dir}")

    rules = []

    # Find all YAML files in the directory
    yaml_files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))

    for yaml_file in yaml_files:
        try:
            # Load YAML content
            with open(yaml_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            # Validate and create RuleConfig
            rule = RuleConfig(**content)

            # Filter by rule_ids if provided
            if rule_ids is None or rule.id in rule_ids:
                rules.append(rule)

        except yaml.YAMLError as e:
            warnings.warn(
                f"Failed to parse YAML file {yaml_file}: {e}. Skipping this file.",
                UserWarning,
            )
            continue

        except Exception as e:
            warnings.warn(
                f"Failed to validate rule from {yaml_file}: {e}. Skipping this file.",
                UserWarning,
            )
            continue

    return rules