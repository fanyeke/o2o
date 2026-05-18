"""Unit tests for YAML rule loader.

Tests the YAML rule configuration parsing logic including:
- Loading rule files from directory
- Parsing rule structure (id, name, description, entity_type, conditions)
- Validating rule conditions (field, operator, value)
- Handling invalid rule files gracefully

Task: T115
Phase: 5 - Rule Engine Configuration and Scanner
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from app.rules.yaml_loader import load_rules, RuleConfig, RuleCondition


class TestRuleCondition:
    """Test cases for RuleCondition model validation."""

    def test_valid_condition_with_gt_operator(self):
        """Test valid condition with greater-than operator."""
        condition = RuleCondition(
            field="redeemed_rate_change",
            operator="gt",
            value=-0.2
        )
        assert condition.field == "redeemed_rate_change"
        assert condition.operator == "gt"
        assert condition.value == -0.2

    def test_valid_condition_with_lt_operator(self):
        """Test valid condition with less-than operator."""
        condition = RuleCondition(
            field="total_receipts_7d",
            operator="lt",
            value=50
        )
        assert condition.field == "total_receipts_7d"
        assert condition.operator == "lt"
        assert condition.value == 50

    def test_valid_condition_with_gte_operator(self):
        """Test valid condition with greater-than-or-equal operator."""
        condition = RuleCondition(
            field="avg_discount_depth",
            operator="gte",
            value=0.3
        )
        assert condition.field == "avg_discount_depth"
        assert condition.operator == "gte"
        assert condition.value == 0.3

    def test_valid_condition_with_lte_operator(self):
        """Test valid condition with less-than-or-equal operator."""
        condition = RuleCondition(
            field="redeemed_rate_30d",
            operator="lte",
            value=0.1
        )
        assert condition.field == "redeemed_rate_30d"
        assert condition.operator == "lte"
        assert condition.value == 0.1

    def test_valid_condition_with_eq_operator(self):
        """Test valid condition with equals operator."""
        condition = RuleCondition(
            field="activity_health_score",
            operator="eq",
            value=0.5
        )
        assert condition.field == "activity_health_score"
        assert condition.operator == "eq"
        assert condition.value == 0.5

    def test_invalid_operator_raises_error(self):
        """Test that invalid operator raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleCondition(
                field="test_field",
                operator="invalid_op",
                value=1.0
            )

        errors = exc_info.value.errors()
        assert any("operator" in str(error).lower() for error in errors)

    def test_missing_field_raises_error(self):
        """Test that missing field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleCondition(
                operator="gt",
                value=1.0
            )

        errors = exc_info.value.errors()
        assert any("field" in str(error).lower() for error in errors)

    def test_missing_operator_raises_error(self):
        """Test that missing operator raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleCondition(
                field="test_field",
                value=1.0
            )

        errors = exc_info.value.errors()
        assert any("operator" in str(error).lower() for error in errors)

    def test_missing_value_raises_error(self):
        """Test that missing value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleCondition(
                field="test_field",
                operator="gt"
            )

        errors = exc_info.value.errors()
        assert any("value" in str(error).lower() for error in errors)


class TestRuleConfig:
    """Test cases for RuleConfig model validation."""

    def test_valid_merchant_rule_config(self):
        """Test valid merchant rule configuration."""
        rule = RuleConfig(
            id="merchant_redeemed_rate_drop",
            name="Merchant Redeemed Rate Drop",
            description="Merchant's 7-day redemption rate dropped significantly",
            entity_type="merchant",
            conditions=[
                RuleCondition(field="redeemed_rate_change", operator="lt", value=-0.2),
                RuleCondition(field="total_receipts_7d", operator="gt", value=200),
            ],
            severity="high"
        )

        assert rule.id == "merchant_redeemed_rate_drop"
        assert rule.name == "Merchant Redeemed Rate Drop"
        assert rule.entity_type == "merchant"
        assert len(rule.conditions) == 2
        assert rule.severity == "high"

    def test_valid_user_rule_config(self):
        """Test valid user rule configuration."""
        rule = RuleConfig(
            id="user_recall",
            name="User Recall",
            description="Inactive user with high historical redemption",
            entity_type="user",
            conditions=[
                RuleCondition(field="days_since_last_receipt", operator="gt", value=30),
                RuleCondition(field="redeemed_rate_30d", operator="gt", value=0.5),
            ],
            severity="medium"
        )

        assert rule.id == "user_recall"
        assert rule.entity_type == "user"
        assert len(rule.conditions) == 2
        assert rule.severity == "medium"

    def test_valid_coupon_rule_config(self):
        """Test valid coupon rule configuration."""
        rule = RuleConfig(
            id="high_discount_low_conversion",
            name="High Discount Low Conversion",
            description="High discount but low redemption rate",
            entity_type="coupon",
            conditions=[
                RuleCondition(field="discount_value", operator="gt", value=0.3),
                RuleCondition(field="redeemed_rate", operator="lt", value=0.1),
            ],
            severity="medium"
        )

        assert rule.id == "high_discount_low_conversion"
        assert rule.entity_type == "coupon"
        assert len(rule.conditions) == 2
        assert rule.severity == "medium"

    def test_invalid_entity_type_raises_error(self):
        """Test that invalid entity_type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleConfig(
                id="test_rule",
                name="Test Rule",
                description="Test rule",
                entity_type="invalid_type",  # Invalid
                conditions=[
                    RuleCondition(field="test", operator="gt", value=1.0)
                ],
                severity="high"
            )

        errors = exc_info.value.errors()
        assert any("entity_type" in str(error).lower() for error in errors)

    def test_missing_conditions_raises_error(self):
        """Test that missing conditions raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleConfig(
                id="test_rule",
                name="Test Rule",
                description="Test rule",
                entity_type="merchant",
                severity="high"
            )

        errors = exc_info.value.errors()
        assert any("conditions" in str(error).lower() for error in errors)

    def test_empty_conditions_raises_error(self):
        """Test that empty conditions list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RuleConfig(
                id="test_rule",
                name="Test Rule",
                description="Test rule",
                entity_type="merchant",
                conditions=[],  # Empty
                severity="high"
            )

        errors = exc_info.value.errors()
        assert any("conditions" in str(error).lower() for error in errors)

    def test_default_severity_is_medium(self):
        """Test that severity defaults to 'medium' if not provided."""
        rule = RuleConfig(
            id="test_rule",
            name="Test Rule",
            description="Test rule",
            entity_type="merchant",
            conditions=[
                RuleCondition(field="test", operator="gt", value=1.0)
            ]
        )

        assert rule.severity == "medium"


class TestLoadRules:
    """Test cases for load_rules function."""

    def test_load_rules_from_valid_directory(self, tmp_path: Path):
        """Test loading rules from a valid directory."""
        # Create test YAML file
        rule_content = """
id: merchant_redeemed_rate_drop
name: Merchant Redeemed Rate Drop
description: Test description
entity_type: merchant
conditions:
  - field: redeemed_rate_change
    operator: lt
    value: -0.2
severity: high
"""
        rule_file = tmp_path / "test_rule.yaml"
        rule_file.write_text(rule_content)

        rules = load_rules(tmp_path)

        assert len(rules) == 1
        assert rules[0].id == "merchant_redeemed_rate_drop"
        assert rules[0].entity_type == "merchant"
        assert len(rules[0].conditions) == 1

    def test_load_rules_from_empty_directory(self, tmp_path: Path):
        """Test loading rules from an empty directory."""
        rules = load_rules(tmp_path)
        assert len(rules) == 0

    def test_load_rules_from_nonexistent_directory(self):
        """Test loading rules from a nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            load_rules(Path("/nonexistent/path/to/rules"))

    def test_load_rules_skips_invalid_yaml(self, tmp_path: Path):
        """Test that invalid YAML files are skipped with warning."""
        # Create valid rule
        valid_rule = tmp_path / "valid.yaml"
        valid_rule.write_text("""
id: valid_rule
name: Valid Rule
description: Valid rule
entity_type: merchant
conditions:
  - field: test
    operator: gt
    value: 1.0
""")

        # Create invalid YAML
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content:")

        # Should load only the valid rule
        rules = load_rules(tmp_path)
        assert len(rules) == 1
        assert rules[0].id == "valid_rule"

    def test_load_rules_skips_invalid_rule_structure(self, tmp_path: Path):
        """Test that rules with invalid structure are skipped."""
        # Create valid rule
        valid_rule = tmp_path / "valid.yaml"
        valid_rule.write_text("""
id: valid_rule
name: Valid Rule
description: Valid rule
entity_type: merchant
conditions:
  - field: test
    operator: gt
    value: 1.0
""")

        # Create rule missing required field
        invalid_rule = tmp_path / "invalid.yaml"
        invalid_rule.write_text("""
id: invalid_rule
name: Invalid Rule
description: Missing entity_type
conditions:
  - field: test
    operator: gt
    value: 1.0
""")

        # Should load only the valid rule
        rules = load_rules(tmp_path)
        assert len(rules) == 1
        assert rules[0].id == "valid_rule"

    def test_load_multiple_rules_from_directory(self, tmp_path: Path):
        """Test loading multiple rules from a directory."""
        # Create multiple rule files
        rule1 = tmp_path / "rule1.yaml"
        rule1.write_text("""
id: rule_1
name: Rule 1
description: First rule
entity_type: merchant
conditions:
  - field: redeemed_rate_change
    operator: lt
    value: -0.2
severity: high
""")

        rule2 = tmp_path / "rule2.yaml"
        rule2.write_text("""
id: rule_2
name: Rule 2
description: Second rule
entity_type: user
conditions:
  - field: days_since_last_receipt
    operator: gt
    value: 30
severity: medium
""")

        rule3 = tmp_path / "rule3.yaml"
        rule3.write_text("""
id: rule_3
name: Rule 3
description: Third rule
entity_type: coupon
conditions:
  - field: discount_value
    operator: gt
    value: 0.3
severity: low
""")

        rules = load_rules(tmp_path)

        assert len(rules) == 3
        rule_ids = {rule.id for rule in rules}
        assert rule_ids == {"rule_1", "rule_2", "rule_3"}

    def test_load_rules_filters_by_rule_ids(self, tmp_path: Path):
        """Test loading rules with specific rule IDs filter."""
        # Create multiple rules
        for i in range(3):
            rule_file = tmp_path / f"rule{i}.yaml"
            rule_file.write_text(f"""
id: rule_{i}
name: Rule {i}
description: Rule {i}
entity_type: merchant
conditions:
  - field: test
    operator: gt
    value: 1.0
""")

        # Load only specific rules
        rules = load_rules(tmp_path, rule_ids=["rule_0", "rule_2"])

        assert len(rules) == 2
        rule_ids = {rule.id for rule in rules}
        assert rule_ids == {"rule_0", "rule_2"}

    def test_load_rules_handles_all_entity_types(self, tmp_path: Path):
        """Test loading rules with all entity types."""
        entity_types = ["merchant", "user", "coupon"]

        for entity_type in entity_types:
            rule_file = tmp_path / f"{entity_type}_rule.yaml"
            rule_file.write_text(f"""
id: {entity_type}_rule
name: {entity_type.title()} Rule
description: {entity_type} rule
entity_type: {entity_type}
conditions:
  - field: test
    operator: gt
    value: 1.0
""")

        rules = load_rules(tmp_path)

        assert len(rules) == 3
        loaded_entity_types = {rule.entity_type for rule in rules}
        assert loaded_entity_types == set(entity_types)

    def test_load_rules_handles_all_operators(self, tmp_path: Path):
        """Test loading rules with all supported operators."""
        operators = ["gt", "lt", "gte", "lte", "eq"]

        for op in operators:
            rule_file = tmp_path / f"rule_{op}.yaml"
            rule_file.write_text(f"""
id: rule_{op}
name: Rule {op}
description: Rule with {op} operator
entity_type: merchant
conditions:
  - field: test_field
    operator: {op}
    value: 1.0
""")

        rules = load_rules(tmp_path)

        assert len(rules) == 5
        for rule in rules:
            assert len(rule.conditions) == 1
            assert rule.conditions[0].operator in operators