from dataclasses import replace

from app.agent import run_agent
from app.config import SETTINGS
from app.models import ExpectedEffect
from app.seed import SCENARIOS
from tests.helpers import make_run


def test_default_completes_with_no_tool_calls():
    run, deps = make_run(SCENARIOS["default"])
    run_agent(run, deps)

    assert run.status == "completed"
    assert run.effects == []


def test_send_followup_autonomous_records_one_effect_and_passes():
    run, deps = make_run(
        SCENARIOS["send_followup"],
        autonomy="autonomous",
        expected=[ExpectedEffect(tool="send_message", match={"contact_id": "c_1"})],
    )
    run_agent(run, deps)

    assert run.status == "completed"
    assert len(run.effects) == 1
    assert run.effects[0].simulated is False
    assert run.verdict.passed is True


def test_three_writes_autonomous_gates_after_budget():
    run, deps = make_run(
        SCENARIOS["three_writes"],
        autonomy="autonomous",
        settings=replace(SETTINGS, max_auto_writes=1),
        reviewer_approves=False,
    )
    run_agent(run, deps)

    assert run.status == "completed"
    assert len(run.effects) == 1  # only the first write got through the budget unchallenged


def test_unknown_tool_completes_rather_than_raising():
    run, deps = make_run(SCENARIOS["unknown_tool"])
    run_agent(run, deps)

    assert run.status == "completed"

def test_tool_error_completes_rather_than_raising():
    run, deps = make_run(SCENARIOS["tool_error"])
    run_agent(run, deps)

    assert run.status == "completed"


def test_never_finishes_fails_instead_of_hanging():
    run, deps = make_run(SCENARIOS["never_finishes"], settings=replace(SETTINGS, max_steps=5))
    run_agent(run, deps)

    assert run.status == "failed"


def test_bad_credentials_fails_without_raising():
    run, deps = make_run(SCENARIOS["bad_credentials"])
    result = run_agent(run, deps)  # should not raise

    assert result.status == "failed"
    assert result.error is not None