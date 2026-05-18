"""Integration tests for rule scanning and decision case creation.

Tests the complete rule scanning workflow including:
- Loading rules from YAML files
- Scanning entity metrics against rule conditions
- Creating DecisionCase for matching entities
- Dry run mode (preview without creating cases)
- Celery task execution

Task: T116
Phase: 5 - Rule Engine Configuration and Scanner
"""

import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rules.yaml_loader import load_rules, RuleConfig
from app.rules.scanner import scan_merchant_rules, create_decision_cases
from app.domain.feature.merchant_metrics import MerchantMetrics
from app.domain.feature.user_metrics import UserMetrics
from app.domain.feature.coupon_metrics import CouponMetrics
from app.domain.application.decision_case import DecisionCase
from app.domain.staging.coupon_receipt_event import CouponReceiptEvent
from app.core.config import get_settings

# Get rules directory from configuration (respects environment settings)
_settings = get_settings()
RULES_DIR = _settings.get_rules_dir()


class TestMerchantRuleScanning:
    """Integration tests for scanning merchant metrics against rules."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_matches_redeemed_rate_drop_rule(self, clean_db: Session):
        """Verify merchant with significant rate drop is matched."""
        # Create merchant metrics that match the rule
        # redeemed_rate_change = (0.15 - 0.30) / 0.30 = -0.5 (50% drop)
        # total_receipts_7d = 250 (above threshold of 200)
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=250,
            redeemed_count_7d=37,
            redeemed_rate_7d=0.15,
            total_receipts_30d=1000,
            redeemed_count_30d=300,
            redeemed_rate_30d=0.30,
            redeemed_rate_change=-0.5,
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        # Load rules from config directory
        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)

        # Filter merchant rules
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        # Scan merchant metrics against rules
        matches = scan_merchant_rules(clean_db, merchant_rules)

        assert len(matches) >= 1

        # Find the match for merchant_001
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_001"),
            None
        )

        assert merchant_match is not None
        assert merchant_match["rule_id"] == "merchant_redeemed_rate_drop"
        assert merchant_match["severity"] == "high"
        assert merchant_match["metrics_snapshot"]["merchant_id"] == "merchant_001"
        assert merchant_match["metrics_snapshot"]["redeemed_rate_change"] == -0.5
        assert merchant_match["metrics_snapshot"]["total_receipts_7d"] == 250

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_no_match_when_rate_change_small(self, clean_db: Session):
        """Verify merchant with small rate change is NOT matched."""
        # redeemed_rate_change = -0.1 (10% drop, below threshold of -0.2)
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_002",
            total_receipts_7d=300,
            redeemed_count_7d=90,
            redeemed_rate_7d=0.30,
            total_receipts_30d=1000,
            redeemed_count_30d=333,
            redeemed_rate_30d=0.33,
            redeemed_rate_change=-0.1,  # Only 10% drop, not enough
            avg_discount_depth=0.20,
            activity_health_score=0.7,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should not match merchant_002
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_002"),
            None
        )

        assert merchant_match is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_no_match_when_volume_small(self, clean_db: Session):
        """Verify merchant with low volume is NOT matched."""
        # redeemed_rate_change = -0.3 (30% drop, above threshold)
        # BUT total_receipts_7d = 50 (below threshold of 200)
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_003",
            total_receipts_7d=50,  # Below threshold
            redeemed_count_7d=10,
            redeemed_rate_7d=0.20,
            total_receipts_30d=200,
            redeemed_count_30d=56,
            redeemed_rate_30d=0.28,
            redeemed_rate_change=-0.3,  # Significant drop but low volume
            avg_discount_depth=0.15,
            activity_health_score=0.5,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should not match merchant_003 due to low volume
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_003"),
            None
        )

        assert merchant_match is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_multiple_merchants_match(self, clean_db: Session):
        """Verify multiple merchants matching the rule."""
        # Create 3 merchants, 2 match the rule
        merchants = [
            # merchant_001: Matches (50% drop, high volume)
            MerchantMetrics(
                merchant_id="merchant_001",
                total_receipts_7d=300,
                redeemed_count_7d=60,
                redeemed_rate_7d=0.20,
                total_receipts_30d=1000,
                redeemed_count_30d=400,
                redeemed_rate_30d=0.40,
                redeemed_rate_change=-0.5,
                avg_discount_depth=0.25,
                activity_health_score=0.6,
                last_activity_date=date.today(),
                updated_at=datetime.now(),
            ),
            # merchant_002: Does NOT match (10% drop)
            MerchantMetrics(
                merchant_id="merchant_002",
                total_receipts_7d=250,
                redeemed_rate_7d=0.27,
                redeemed_rate_30d=0.30,
                redeemed_rate_change=-0.1,
                avg_discount_depth=0.20,
                activity_health_score=0.7,
                last_activity_date=date.today(),
                updated_at=datetime.now(),
            ),
            # merchant_003: Matches (25% drop, high volume)
            MerchantMetrics(
                merchant_id="merchant_003",
                total_receipts_7d=400,
                redeemed_count_7d=80,
                redeemed_rate_7d=0.20,
                total_receipts_30d=1600,
                redeemed_count_30d=512,
                redeemed_rate_30d=0.32,
                redeemed_rate_change=-0.375,
                avg_discount_depth=0.30,
                activity_health_score=0.55,
                last_activity_date=date.today(),
                updated_at=datetime.now(),
            ),
        ]

        clean_db.bulk_save_objects(merchants)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should match 2 merchants
        assert len(matches) == 2

        matched_ids = {m["merchant_id"] for m in matches}
        assert matched_ids == {"merchant_001", "merchant_003"}

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_with_null_metrics(self, clean_db: Session):
        """Verify merchant with NULL metrics is NOT matched."""
        # Merchant with NULL redeemed_rate_change (no prior data)
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_null",
            total_receipts_7d=250,
            redeemed_rate_7d=0.20,
            redeemed_rate_30d=None,  # No 30-day data
            redeemed_rate_change=None,  # Cannot calculate change
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should not match merchant with NULL metrics
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_null"),
            None
        )

        assert merchant_match is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_with_multiple_conditions_all_required(self, clean_db: Session):
        """Verify all conditions must be satisfied (AND logic)."""
        # Merchant that satisfies only ONE condition (NOT both)
        # redeemed_rate_change = -0.3 (satisfies condition 1)
        # BUT total_receipts_7d = 100 (fails condition 2)
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_partial",
            total_receipts_7d=100,  # Fails volume condition
            redeemed_rate_7d=0.21,
            redeemed_rate_30d=0.30,
            redeemed_rate_change=-0.3,  # Satisfies rate change condition
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should NOT match (AND logic requires both conditions)
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_partial"),
            None
        )

        assert merchant_match is None


class TestCreateDecisionCases:
    """Integration tests for creating DecisionCase from rule matches."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_create_decision_case_from_match(self, clean_db: Session):
        """Verify DecisionCase is created correctly from rule match."""
        # Create merchant metrics that match the rule
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=250,
            redeemed_count_7d=37,
            redeemed_rate_7d=0.15,
            total_receipts_30d=1000,
            redeemed_count_30d=300,
            redeemed_rate_30d=0.30,
            redeemed_rate_change=-0.5,
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Create decision cases (NOT dry run)
        cases = create_decision_cases(clean_db, matches, dry_run=False)

        assert len(cases) == 1

        case = cases[0]
        assert case.case_type == "商户异常"  # Mapped from merchant rule
        assert case.severity_level == "high"
        assert case.merchant_id == "merchant_001"
        assert case.trigger_rule_id == "merchant_redeemed_rate_drop"
        assert case.status == "pending"
        assert case.trigger_metrics_snapshot is not None
        assert case.trigger_metrics_snapshot["redeemed_rate_change"] == -0.5

        # Verify case is persisted in database
        db_case = clean_db.query(DecisionCase).filter(
            DecisionCase.merchant_id == "merchant_001"
        ).first()

        assert db_case is not None
        assert db_case.id == case.id
        assert db_case.status == "pending"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_create_decision_cases_dry_run_mode(self, clean_db: Session):
        """Verify dry run mode returns preview without creating cases."""
        # Create merchant metrics
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=250,
            redeemed_rate_7d=0.15,
            redeemed_rate_30d=0.30,
            redeemed_rate_change=-0.5,
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Dry run mode (should NOT create cases)
        cases_preview = create_decision_cases(clean_db, matches, dry_run=True)

        assert len(cases_preview) == 1

        case_preview = cases_preview[0]
        assert case_preview.merchant_id == "merchant_001"
        assert case_preview.case_type == "商户异常"  # Mapped from merchant rule

        # Verify NO case is persisted in database
        db_case = clean_db.query(DecisionCase).filter(
            DecisionCase.merchant_id == "merchant_001"
        ).first()

        assert db_case is None  # Dry run should NOT persist

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_create_decision_cases_multiple_matches(self, clean_db: Session):
        """Verify multiple DecisionCases are created for multiple matches."""
        # Create 2 merchants that match
        merchants = [
            MerchantMetrics(
                merchant_id=f"merchant_{i:03d}",
                total_receipts_7d=300,
                redeemed_rate_7d=0.20,
                redeemed_rate_30d=0.40,
                redeemed_rate_change=-0.5,
                avg_discount_depth=0.25,
                activity_health_score=0.6,
                last_activity_date=date.today(),
                updated_at=datetime.now(),
            )
            for i in range(1, 3)  # merchant_001, merchant_002
        ]

        clean_db.bulk_save_objects(merchants)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        cases = create_decision_cases(clean_db, matches, dry_run=False)

        assert len(cases) == 2

        # Verify both cases are persisted
        db_cases = clean_db.query(DecisionCase).all()
        assert len(db_cases) == 2

        db_merchant_ids = {case.merchant_id for case in db_cases}
        assert db_merchant_ids == {"merchant_001", "merchant_002"}

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_create_decision_case_preserves_metrics_snapshot(self, clean_db: Session):
        """Verify metrics snapshot is correctly preserved in DecisionCase."""
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_snapshot",
            total_receipts_7d=250,
            redeemed_count_7d=37,
            redeemed_rate_7d=0.148,  # Specific value
            total_receipts_30d=1000,
            redeemed_count_30d=300,
            redeemed_rate_30d=0.300,  # Specific value
            redeemed_rate_change=-0.507,  # Specific value
            avg_discount_depth=0.247,  # Specific value
            activity_health_score=0.618,  # Specific value
            last_activity_date=date.today() - timedelta(days=2),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)
        cases = create_decision_cases(clean_db, matches, dry_run=False)

        case = cases[0]
        snapshot = case.trigger_metrics_snapshot

        # Verify all metric values are preserved
        assert snapshot["merchant_id"] == "merchant_snapshot"
        assert snapshot["total_receipts_7d"] == 250
        assert snapshot["redeemed_rate_7d"] == pytest.approx(0.148, rel=0.01)
        assert snapshot["redeemed_rate_30d"] == pytest.approx(0.300, rel=0.01)
        assert snapshot["redeemed_rate_change"] == pytest.approx(-0.507, rel=0.01)
        assert snapshot["avg_discount_depth"] == pytest.approx(0.247, rel=0.01)
        assert snapshot["activity_health_score"] == pytest.approx(0.618, rel=0.01)

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_create_decision_case_with_empty_matches(self, clean_db: Session):
        """Verify behavior when no merchants match rules."""
        # Create merchants that don't match
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_no_match",
            total_receipts_7d=50,  # Below threshold
            redeemed_rate_change=-0.1,  # Below threshold
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should return empty matches
        assert len(matches) == 0

        # Should create no cases
        cases = create_decision_cases(clean_db, matches, dry_run=False)
        assert len(cases) == 0

        # Verify database has no decision cases
        db_cases = clean_db.query(DecisionCase).all()
        assert len(db_cases) == 0


class TestRuleScanWorkflow:
    """Integration tests for complete rule scanning workflow."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_full_workflow_scan_and_create_cases(self, clean_db: Session):
        """Verify complete workflow from loading rules to creating cases."""
        # Setup: Create feature metrics data
        merchants = [
            # 2 merchants that match the rule
            MerchantMetrics(
                merchant_id=f"merchant_match_{i}",
                total_receipts_7d=300,
                redeemed_rate_7d=0.20,
                redeemed_rate_30d=0.40,
                redeemed_rate_change=-0.5,
                avg_discount_depth=0.25,
                activity_health_score=0.6,
                last_activity_date=date.today(),
                updated_at=datetime.now(),
            )
            for i in range(1, 3)
        ]

        # 1 merchant that doesn't match
        merchants.append(MerchantMetrics(
            merchant_id="merchant_no_match",
            total_receipts_7d=50,
            redeemed_rate_change=-0.1,
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        ))

        clean_db.bulk_save_objects(merchants)
        clean_db.commit()

        # Step 1: Load rules from YAML files
        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        # Step 2: Scan merchant metrics against rules
        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should match 2 merchants
        assert len(matches) == 2

        # Step 3: Create decision cases
        cases = create_decision_cases(clean_db, matches, dry_run=False)

        # Should create 2 cases
        assert len(cases) == 2

        # Step 4: Verify cases in database
        db_cases = clean_db.query(DecisionCase).all()
        assert len(db_cases) == 2

        # All cases should be in pending status
        for case in db_cases:
            assert case.status == "pending"
            assert case.trigger_rule_id == "merchant_redeemed_rate_drop"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_workflow_with_specific_rule_ids_filter(self, clean_db: Session):
        """Verify workflow when filtering by specific rule IDs."""
        # Setup: Create merchant metrics
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=300,
            redeemed_rate_7d=0.20,
            redeemed_rate_30d=0.40,
            redeemed_rate_change=-0.5,
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        # Load only specific rule
        rules_dir = RULES_DIR
        rules = load_rules(rules_dir, rule_ids=["merchant_redeemed_rate_drop"])
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        # Should only have 1 rule
        assert len(merchant_rules) == 1
        assert merchant_rules[0].id == "merchant_redeemed_rate_drop"

        # Scan and create cases
        matches = scan_merchant_rules(clean_db, merchant_rules)
        cases = create_decision_cases(clean_db, matches, dry_run=False)

        assert len(cases) == 1
        assert cases[0].trigger_rule_id == "merchant_redeemed_rate_drop"

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_workflow_with_no_rules_loaded(self, clean_db: Session):
        """Verify workflow when no rules are loaded."""
        # Setup: Create merchant metrics
        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_001",
            total_receipts_7d=300,
            redeemed_rate_change=-0.5,
            avg_discount_depth=0.25,
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        # Load rules with filter that returns no rules
        rules_dir = RULES_DIR
        rules = load_rules(rules_dir, rule_ids=["nonexistent_rule"])
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        # Should have no rules
        assert len(merchant_rules) == 0

        # Scan should return empty matches
        matches = scan_merchant_rules(clean_db, merchant_rules)
        assert len(matches) == 0

        # Should create no cases
        cases = create_decision_cases(clean_db, matches, dry_run=False)
        assert len(cases) == 0


class TestRuleScannerEdgeCases:
    """Integration tests for edge cases in rule scanning."""

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_with_empty_merchant_metrics_table(self, clean_db: Session):
        """Verify behavior when merchant metrics table is empty."""
        # No merchant metrics in database

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should return empty matches
        assert len(matches) == 0

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_with_boundary_values(self, clean_db: Session):
        """Verify merchant with exactly threshold values."""
        # redeemed_rate_change = -0.2 (exactly threshold)
        # total_receipts_7d = 200 (exactly threshold)
        # This should MATCH because conditions use < and > (not <= and >=)
        # The rule uses: operator: lt (less than) and operator: gt (greater than)

        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_boundary",
            total_receipts_7d=200,  # Exactly threshold, BUT operator is gt (must be > 200)
            redeemed_rate_7d=0.16,
            redeemed_rate_30d=0.20,
            redeemed_rate_change=-0.2,  # Exactly threshold, BUT operator is lt (must be < -0.2)
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should NOT match because:
        # - redeemed_rate_change = -0.2 is NOT < -0.2
        # - total_receipts_7d = 200 is NOT > 200
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_boundary"),
            None
        )

        assert merchant_match is None

    @pytest.mark.skip(reason="需要PostgreSQL数据库环境")
    def test_scan_merchant_with_just_above_threshold(self, clean_db: Session):
        """Verify merchant just above threshold values."""
        # redeemed_rate_change = -0.21 (just below -0.2)
        # total_receipts_7d = 201 (just above 200)
        # This SHOULD match

        merchant_metrics = MerchantMetrics(
            merchant_id="merchant_just_above",
            total_receipts_7d=201,  # Just above threshold (> 200)
            redeemed_rate_7d=0.158,
            redeemed_rate_30d=0.20,
            redeemed_rate_change=-0.21,  # Just below threshold (< -0.2)
            avg_discount_depth=0.25,
            activity_health_score=0.6,
            last_activity_date=date.today(),
            updated_at=datetime.now(),
        )

        clean_db.add(merchant_metrics)
        clean_db.commit()

        rules_dir = RULES_DIR
        rules = load_rules(rules_dir)
        merchant_rules = [r for r in rules if r.entity_type == "merchant"]

        matches = scan_merchant_rules(clean_db, merchant_rules)

        # Should match
        merchant_match = next(
            (m for m in matches if m["merchant_id"] == "merchant_just_above"),
            None
        )

        assert merchant_match is not None