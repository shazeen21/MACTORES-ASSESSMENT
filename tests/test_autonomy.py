import pytest

from app.autonomy import evaluate_gate


@pytest.mark.parametrize(
    "level,tool_kind,writes_so_far,max_auto_writes,expect_allow,expect_simulate,expect_approval",
    [
        ("shadow", "read", 0, 2, True, False, False),
        ("supervised", "read", 5, 2, True, False, False),
        ("autonomous", "read", 5, 2, True, False, False),
        ("shadow", "write", 0, 2, True, True, False),
        ("supervised", "write", 0, 2, False, False, True),
        ("autonomous", "write", 0, 2, True, False, False),
        ("autonomous", "write", 1, 2, True, False, False),
        ("autonomous", "write", 2, 2, False, False, True),
    ],
)
def test_evaluate_gate(
    level, tool_kind, writes_so_far, max_auto_writes,
    expect_allow, expect_simulate, expect_approval,
):
    decision = evaluate_gate(level, tool_kind, writes_so_far, max_auto_writes)
    assert decision.allow == expect_allow
    assert decision.simulate == expect_simulate
    assert decision.requires_approval == expect_approval
    assert decision.reason