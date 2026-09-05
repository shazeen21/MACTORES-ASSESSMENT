"""Governed autonomy: how much the agent is allowed to do on its own.

This is the smallest file in the project and one of the most important. An agent that can send
messages and update records needs a policy sitting between "the model asked for this" and "it
happened". That policy is one pure function.

TASK 1: evaluate_gate.
"""

from __future__ import annotations

from app.config import SETTINGS
from app.models import AutonomyLevel, GateDecision, ToolKind


def evaluate_gate(
    level: AutonomyLevel,
    tool_kind: ToolKind,
    writes_so_far: int,
    max_auto_writes: int = SETTINGS.max_auto_writes,
) -> GateDecision:
    if tool_kind == "read":
        return GateDecision(allow=True, reason="reads are always allowed")

    if level == "shadow":
        return GateDecision(
            allow=True, simulate=True, reason="shadow mode: write simulated, not executed"
        )

    if level == "supervised":
        return GateDecision(
            allow=False, requires_approval=True, reason="supervised: every write needs approval"
        )

    # level == "autonomous"
    if writes_so_far < max_auto_writes:
        return GateDecision(
            allow=True,
            reason=f"autonomous write {writes_so_far + 1}/{max_auto_writes} within budget",
        )
    return GateDecision(
        allow=False,
        requires_approval=True,
        reason=f"autonomous write budget of {max_auto_writes} exhausted",
    )