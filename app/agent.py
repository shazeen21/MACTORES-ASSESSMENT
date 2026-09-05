"""The agent loop. This is the centrepiece of the exercise.

An "agent" here is not magic. It's a loop:

    ask the model what to do  →  do it  →  tell the model what happened  →  repeat

…until the model says it's finished, or we run out of turns. Everything else in this project exists
to make that loop safe: the gate decides whether a step is allowed, the verifier checks afterwards
that the right things happened, the retry keeps a flaky provider from killing the run.

PROVIDED: AgentDeps, and the helpers `_decide`, `_emit`, `_ask_reviewer`, `_execute`, `_observation`.
TASK 3:   run_agent.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import ValidationError

from app.autonomy import evaluate_gate
from app.config import SETTINGS, Settings
from app.model_client import ModelClient, complete_with_retry
from app.models import AgentIntent, Effect, Run, Step, Task
from app.store import Store
from app.tools import ToolDef, ToolError, Workspace
from app.verifier import verify

SYSTEM_PROMPT = (
    "You are an automation agent. On each turn reply with ONLY a JSON object matching this schema:\n"
    '{"intent": "tool_use"|"final", "thought": str, "tool": str|null, '
    '"args": object, "answer": str|null}.\n'
    "Use tool_use to call a tool, or final with an answer when the task is done."
)


class AgentDeps:
    """Everything a run needs, handed in from outside rather than imported.

    This is dependency injection, and it's the reason this project is testable at all. `run_agent`
    never reaches for a global model or a global store — it uses what it was given. So a test can
    hand it a scripted model and a throwaway Store, and there's nothing to clean up afterwards.
    See `make_run` in tests/helpers.py, which does exactly that.
    """

    def __init__(
        self,
        model: ModelClient,
        workspace: Workspace,
        registry: dict[str, ToolDef],
        store: Store,
        settings: Settings = SETTINGS,
    ):
        self.model = model
        self.workspace = workspace
        self.registry = registry
        self.store = store
        self.settings = settings

def run_agent(run: Run, deps: AgentDeps) -> Run:
    task = deps.store.get_task(run.task_id)
    messages = initial_messages(task.goal)
    writes_done = 0
    run.status = "running"

    try:
        for _ in range(deps.settings.max_steps):
            # 1. DECIDE
            intent = _decide(deps, messages)
            if intent is None:
                _emit(run, "error", message="model never produced valid JSON", ok=False)
                run.status = "failed"
                run.error = "model never produced valid JSON"
                break

            # 2. FINISHED?
            if intent.intent == "final":
                _emit(run, "final", message=intent.answer or "")
                run.status = "completed"
                break

            # 3. FIND THE TOOL
            tool = deps.registry.get(intent.tool)
            if tool is None:
                _emit(run, "tool_result", tool=intent.tool, ok=False,
                      message=f"unknown tool: {intent.tool}")
                messages.append(
                    {"role": "user", "content": _observation({"error": f"unknown tool {intent.tool!r}"})}
                )
                continue

            # 4. GATE IT
            decision = evaluate_gate(
                run.autonomy, tool.kind, writes_done, deps.settings.max_auto_writes
            )
            _emit(run, "gate", message=decision.reason)

            if decision.requires_approval:
                approved = _ask_reviewer(task, run, deps)
                if not approved:
                    _emit(run, "tool_result", tool=tool.name, ok=False,
                          message="reviewer rejected the write")
                    messages.append(
                        {"role": "user", "content": _observation({"error": "reviewer rejected this write"})}
                    )
                    continue

            # 5. RUN IT
            _emit(run, "tool_call", tool=tool.name, args=intent.args)
            result, ok = _execute(tool, intent.args, run, decision.simulate)
            _emit(run, "tool_result", tool=tool.name, result=result, ok=ok)

            if ok and tool.kind == "write":
                run.effects.append(
                    Effect(tool=tool.name, args=dict(intent.args), simulated=decision.simulate)
                )
                writes_done += 1

            # 6. TELL THE MODEL
            messages.append({"role": "user", "content": _observation(result)})
        else:
            # loop finished all max_steps iterations without hitting `break`
            _emit(run, "error", message="max_steps reached without a final answer", ok=False)
            run.status = "failed"
            run.error = "max_steps reached without a final answer"

    except Exception as exc:  # FatalError from the model, or anything unexpected
        _emit(run, "error", message=str(exc), ok=False)
        run.status = "failed"
        run.error = str(exc)

    if run.status == "completed":
        run.verdict = verify(task, run)

    return run

# ─── Provided helpers ─────────────────────────────────────────────────────────────────────────


def _decide(deps: AgentDeps, messages: list[dict]) -> Optional[AgentIntent]:
    """Ask the model what to do next, and insist on a well-formed answer.

    PROVIDED — read it, it's the structured-output pattern you'd write by hand at work.

    The model returns text. We try to parse that text into an AgentIntent. If it isn't valid we
    tell the model so and ask again, up to `settings.parse_max_retries` times. Returns None if it
    never manages it, which the caller treats as a failed run.
    """
    raw = complete_with_retry(deps.model, messages, deps.settings)
    for attempt in range(deps.settings.parse_max_retries + 1):
        try:
            return AgentIntent.model_validate_json(raw)
        except ValidationError:
            if attempt >= deps.settings.parse_max_retries:
                return None
            messages.append(
                {
                    "role": "user",
                    "content": "Your last reply was not valid JSON for the schema. "
                    "Reply with ONLY the JSON object.",
                }
            )
            raw = complete_with_retry(deps.model, messages, deps.settings)
    return None


def _emit(run: Run, step_type: str, **fields: Any) -> Step:
    """Append a Step to the run's trail and return it.

        _emit(run, "gate", message=decision.reason)
        _emit(run, "tool_result", tool=name, result=result, ok=False)

    PROVIDED. Use it for every observable event.
    """
    step = Step(index=len(run.steps), type=step_type, **fields)  # type: ignore[arg-type]
    run.steps.append(step)
    return step


def _ask_reviewer(task: Task, run: Run, deps: AgentDeps) -> bool:
    """Ask the human reviewer whether this write may proceed.

    PROVIDED. In the real product this suspends the run, notifies a reviewer, and waits for them
    to click approve or reject. Here the answer is `task.reviewer_approves`, decided when the task
    was created — the same trick as the scripted model, and for the same reason: a test can't wait
    for a human.

    What matters is that your loop handles BOTH answers correctly, not how the answer arrives.
    """
    approved = task.reviewer_approves
    _emit(
        run,
        "gate",
        message=f"reviewer {'approved' if approved else 'rejected'} the write",
        ok=approved,
    )
    return approved


def _execute(tool: ToolDef, args: dict, run: Run, simulate: bool) -> tuple[Any, bool]:
    """Run a tool, or pretend to. Returns (result, ok).

    PROVIDED. Three things happen here:

      - in simulate mode (shadow), the tool is never called. We return a marker result instead.
        This is the line that makes shadow mode risk-free.
      - for `send_message`, an idempotency key is generated from the run id and the step count,
        so the same logical send always carries the same key. This is the key your TASK 4b
        implementation remembers.
      - a ToolError is caught and turned into (error_dict, False) rather than being allowed to
        propagate — which is how your loop gets to treat a tool failure as an observation instead
        of a crash.
    """
    if simulate:
        return {"simulated": True, "note": "shadow mode: the side effect was not executed"}, True

    if tool.name == "send_message" and "idempotency_key" not in args:
        args["idempotency_key"] = f"{run.id}:{len(run.steps)}"

    try:
        return tool.func(**args), True
    except ToolError as exc:
        return {"error": str(exc)}, False


def _observation(result: Any) -> str:
    """Format a tool result as the message the model sees next turn. PROVIDED."""
    return f"Observation: {json.dumps(result, default=str)}"


def initial_messages(goal: str) -> list[dict]:
    """The opening conversation: the system prompt, then the goal. PROVIDED."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {goal}"},
    ]


# Re-exported so tests and the API can import them from one place.
__all__ = [
    "AgentDeps",
    "run_agent",
    "initial_messages",
    "evaluate_gate",
    "verify",
    "Effect",
]
