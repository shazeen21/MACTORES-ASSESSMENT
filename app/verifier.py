"""Behaviour-equivalence checking: did the agent do what it was supposed to, and nothing else?

An agent that finishes and says "done!" has told you nothing. The model's own summary of its work
is not evidence. So after every run we compare the side effects the task *expected* against the
effects that *actually happened*, and that diff is the verdict.

This is the part that makes shadow mode valuable. Effects recorded in shadow mode are simulated,
but the diff works exactly the same on them — so you can prove an agent would have behaved
correctly before you ever let it touch production.

TASK 2: verify.
"""

from __future__ import annotations

from app.models import Run, Task, Verdict


def verify(task: Task, run: Run) -> Verdict:
    matched = []
    missing = []
    used_indices: set[int] = set()

    for expected in task.expected_effects:
        found_index = None
        for i, effect in enumerate(run.effects):
            if i in used_indices:
                continue
            if effect.tool != expected.tool:
                continue
            if all(effect.args.get(k) == v for k, v in expected.match.items()):
                found_index = i
                break
        if found_index is not None:
            matched.append(expected)
            used_indices.add(found_index)
        else:
            missing.append(expected)

    unexpected = [effect for i, effect in enumerate(run.effects) if i not in used_indices]

    passed = not missing and not unexpected

    return Verdict(
        passed=passed,
        matched=matched,
        missing=missing,
        unexpected=unexpected,
        mode=run.autonomy,
        detail=f"{len(matched)} matched, {len(missing)} missing, {len(unexpected)} unexpected",
    )
