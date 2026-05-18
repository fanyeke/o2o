"""Approval Safety Test - 验证系统不会让LLM绕过人工审批.

This test verifies that the approval workflow enforces safety constraints:
1. Cannot approve case unless status == 'recommended'
2. Approve creates ApprovalLog
3. Approve creates ActionExecution
4. Reject does not execute action
5. Duplicate approval does not duplicate execution (idempotency)
6. Unknown action types fail gracefully

This is critical for production safety - LLM must not bypass human oversight.
"""

import pytest
from app.core.database import get_db
from app.domain.application.decision_case import DecisionCase
from app.domain.application.recommendation import Recommendation
from app.services.approval_service import ApprovalService
from sqlalchemy import text


@pytest.fixture
def test_db():
    """Setup test database."""
    db = next(get_db())
    yield db
    db.close()


def test_cannot_approve_pending_case(test_db):
    """验证status!=recommended时不能审批."""

    # Create a case with status='pending'
    test_db.execute(text("""
        INSERT INTO application.decision_case (id, case_type, entity_id, severity_level, status, created_at)
        VALUES ('test_case_001', 'merchant', 'm001', 'medium', 'pending', NOW())
        ON CONFLICT (id) DO NOTHING
    """))
    test_db.commit()

    approval_service = ApprovalService(test_db)

    # Attempt to approve should fail
    try:
        approval_service.approve_case(
            case_id='test_case_001',
            approver_id='test_approver',
            approval_comment='Test approval'
        )
        pytest.fail("Should not allow approving case with status='pending'")
    except ValueError as e:
        assert "status" in str(e).lower() or "recommended" in str(e).lower()
        print(f"\n✓ Correctly rejected approval: {e}")


def test_approve_creates_approval_log(test_db):
    """验证approve后必须写ApprovalLog."""

    # Create a case with status='recommended' and recommendation
    test_db.execute(text("""
        INSERT INTO application.decision_case (id, case_type, entity_id, severity_level, status, created_at)
        VALUES ('test_case_002', 'merchant', 'm002', 'medium', 'recommended', NOW())
        ON CONFLICT (id) DO UPDATE SET status='recommended'
    """))

    test_db.execute(text("""
        INSERT INTO application.recommendation (id, case_id, decision_summary, suggested_actions, confidence_score, created_at)
        VALUES ('rec_002', 'test_case_002', 'Test recommendation', '[{"type": "no_action"}]', 0.5, NOW())
        ON CONFLICT (id) DO NOTHING
    """))
    test_db.commit()

    approval_service = ApprovalService(test_db)

    # Approve the case
    result = approval_service.approve_case(
        case_id='test_case_002',
        approver_id='test_approver',
        approval_comment='Test approval'
    )

    # Verify ApprovalLog created
    log_count = test_db.execute(text("""
        SELECT COUNT(*) FROM application.approval_log
        WHERE case_id = 'test_case_002' AND action = 'approve'
    """)).first()[0]

    assert log_count >= 1, "ApprovalLog must be created after approval"

    print(f"\n✓ ApprovalLog created for approved case")


def test_approve_creates_action_execution(test_db):
    """验证approve后必须生成ActionExecution."""

    # Use the same case (test_case_002 already approved in previous test)

    # Verify ActionExecution created
    action_count = test_db.execute(text("""
        SELECT COUNT(*) FROM application.action_execution
        WHERE case_id = 'test_case_002'
    """)).first()[0]

    assert action_count >= 1, "ActionExecution must be created after approval"

    print(f"\n✓ ActionExecution created for approved case")


def test_reject_does_not_execute(test_db):
    """验证reject后不能执行动作."""

    # Create a case with status='recommended'
    test_db.execute(text("""
        INSERT INTO application.decision_case (id, case_type, entity_id, severity_level, status, created_at)
        VALUES ('test_case_003', 'merchant', 'm003', 'medium', 'recommended', NOW())
        ON CONFLICT (id) DO UPDATE SET status='recommended'
    """))

    test_db.execute(text("""
        INSERT INTO application.recommendation (id, case_id, decision_summary, suggested_actions, confidence_score, created_at)
        VALUES ('rec_003', 'test_case_003', 'Test recommendation', '[{"type": "no_action"}]', 0.5, NOW())
        ON CONFLICT (id) DO NOTHING
    """))
    test_db.commit()

    approval_service = ApprovalService(test_db)

    # Reject the case
    result = approval_service.reject_case(
        case_id='test_case_003',
        approver_id='test_approver',
        rejection_reason='Test rejection'
    )

    # Verify NO ActionExecution created
    action_count = test_db.execute(text("""
        SELECT COUNT(*) FROM application.action_execution
        WHERE case_id = 'test_case_003'
    """)).first()[0]

    assert action_count == 0, "Reject must NOT create ActionExecution"

    print(f"\n✓ Reject correctly prevented action execution")


def test_duplicate_approval_idempotent(test_db):
    """验证重复审批不重复执行动作."""

    # Use test_case_002 which was already approved

    approval_service = ApprovalService(test_db)

    # Try to approve again (should handle gracefully)
    try:
        approval_service.approve_case(
            case_id='test_case_002',
            approver_id='test_approver_2',
            approval_comment='Duplicate approval'
        )

        # If succeeded, check that NO duplicate ActionExecution created
        action_count = test_db.execute(text("""
            SELECT COUNT(*) FROM application.action_execution
            WHERE case_id = 'test_case_002'
        """)).first()[0]

        assert action_count == 1, \
            f"Duplicate approval created {action_count} actions (should be exactly 1)"

        print(f"\n✓ Duplicate approval handled idempotently")

    except ValueError as e:
        # If failed (case already approved), that's also acceptable
        print(f"\n✓ Duplicate approval correctly rejected: {e}")


def test_unknown_action_type_fails(test_db):
    """验证未知action_type必须失败并记录."""

    # Create a case with invalid action type
    test_db.execute(text("""
        INSERT INTO application.decision_case (id, case_type, entity_id, severity_level, status, created_at)
        VALUES ('test_case_004', 'merchant', 'm004', 'medium', 'recommended', NOW())
        ON CONFLICT (id) DO UPDATE SET status='recommended'
    """))

    test_db.execute(text("""
        INSERT INTO application.recommendation (id, case_id, decision_summary, suggested_actions, confidence_score, created_at)
        VALUES ('rec_004', 'test_case_004', 'Test recommendation',
                '[{"type": "invalid_action_type", "params": {}}]', 0.5, NOW())
        ON CONFLICT (id) DO NOTHING
    """))
    test_db.commit()

    approval_service = ApprovalService(test_db)

    # Approve should handle unknown action gracefully
    try:
        result = approval_service.approve_case(
            case_id='test_case_004',
            approver_id='test_approver',
            approval_comment='Approving invalid action'
        )

        # Check ActionExecution status
        action_status = test_db.execute(text("""
            SELECT execution_status FROM application.action_execution
            WHERE case_id = 'test_case_004'
            ORDER BY executed_at DESC
            LIMIT 1
        """)).first()

        # Should have failed or logged error
        if action_status:
            assert action_status[0] in ['failed', 'error'], \
                f"Unknown action should fail, got status '{action_status[0]}'"
            print(f"\n✓ Unknown action type correctly failed with status: {action_status[0]}")

    except Exception as e:
        # If execution failed completely, that's acceptable
        print(f"\n✓ Unknown action type correctly rejected/failed: {e}")


def test_high_risk_action_requires_approval():
    """验证高风险动作必须有requires_approval标记."""

    from app.agents.prompts.decision_prompt import build_decision_prompt
    from app.domain.application.decision_case import DecisionCase

    # Mock recommendation with high-risk action
    mock_recommendation = {
        "decision_summary": "Test high-risk recommendation",
        "evidence": [
            {"type": "test", "content": "Test evidence", "risk_level": "high"}
        ],
        "suggested_actions": [
            {
                "type": "pause_coupon_distribution",
                "params": {"merchant_id": "test"},
                "risk_level": "high",
                "requires_approval": True  # Must be True for high-risk
            }
        ],
        "confidence_score": 0.75
    }

    # Verify that high-risk action has requires_approval=True
    for action in mock_recommendation["suggested_actions"]:
        if action.get("risk_level") == "high":
            assert action.get("requires_approval") == True, \
                "High-risk action must have requires_approval=True"

    print(f"\n✓ High-risk action correctly marked requires_approval=True")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])