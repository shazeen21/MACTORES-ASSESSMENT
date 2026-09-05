from app.models import Effect, ExpectedEffect, Run, Task
from app.verifier import verify


def _task(expected):
    return Task(
        id="t1", goal="g", scenario="s", autonomy="autonomous", expected_effects=expected
    )


def _run(effects, autonomy="autonomous"):
    return Run(id="r1", task_id="t1", autonomy=autonomy, effects=effects)


def test_everything_expected_happened_and_nothing_else():
    task = _task([ExpectedEffect(tool="send_message", match={"contact_id": "c_1"})])
    run = _run([Effect(tool="send_message", args={"contact_id": "c_1", "body": "hi"})])

    verdict = verify(task, run)

    assert verdict.passed is True
    assert len(verdict.matched) == 1
    assert verdict.missing == []
    assert verdict.unexpected == []


def test_expected_effect_never_happened_is_missing():
    task = _task([ExpectedEffect(tool="send_message", match={"contact_id": "c_1"})])
    run = _run([])

    verdict = verify(task, run)

    assert verdict.passed is False
    assert len(verdict.missing) == 1


def test_effect_nobody_asked_for_is_unexpected():
    task = _task([])
    run = _run([Effect(tool="send_message", args={"contact_id": "c_1"})])

    verdict = verify(task, run)

    assert verdict.passed is False
    assert len(verdict.unexpected) == 1


def test_simulated_effects_are_treated_identically():
    task = _task([ExpectedEffect(tool="send_message", match={"contact_id": "c_1"})])
    run = _run(
        [Effect(tool="send_message", args={"contact_id": "c_1"}, simulated=True)],
        autonomy="shadow",
    )

    verdict = verify(task, run)

    assert verdict.passed is True
    assert verdict.mode == "shadow"


def test_one_effect_cannot_satisfy_two_expectations():
    task = _task(
        [
            ExpectedEffect(tool="send_message", match={"contact_id": "c_1"}),
            ExpectedEffect(tool="send_message", match={"contact_id": "c_1"}),
        ]
    )
    run = _run([Effect(tool="send_message", args={"contact_id": "c_1"})])

    verdict = verify(task, run)

    assert verdict.passed is False
    assert len(verdict.matched) == 1
    assert len(verdict.missing) == 1