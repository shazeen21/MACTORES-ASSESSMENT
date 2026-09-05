"""The HTTP surface. FastAPI routes.

Four endpoints. Three are provided as worked examples; the fourth is TASK 5, and it's the one that
makes the whole thing runnable from a browser.

Everything here is synchronous — plain `def`, not `async def`. FastAPI handles both, and running a
whole agent loop inline in the request is perfectly reasonable at this scale. (In production a run
takes minutes and goes on a queue, which is why the real service is async. Out of scope here.)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import AgentDeps, run_agent
from app.config import SETTINGS
from app.model_client import MockModelClient
from app.models import Run, Task, TaskSpec
from app.seed import CONTACTS, script_for
from app.store import store
from app.tools import Workspace, build_registry

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@router.post("/tasks", response_model=Task)
def create_task(spec: TaskSpec) -> Task:
    """PROVIDED. Note how little there is to it: FastAPI validated the body into a TaskSpec
    before this function was even called, using the model in app/models.py."""
    task = Task(id=_new_id("t"), **spec.model_dump())
    store.add_task(task)
    return task


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str) -> Task:
    """PROVIDED — your worked example of a path parameter and a 404."""
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    return task


class StartRunBody(BaseModel):
    task_id: str


@router.post("/runs", response_model=Run, status_code=201)
def start_run(body: StartRunBody) -> Run:
    task = store.get_task(body.task_id)
    if task is None:
        raise HTTPException(404, "task not found")

    run = Run(id=_new_id("r"), task_id=task.id, autonomy=task.autonomy)
    store.add_run(run)

    ws = Workspace(CONTACTS)
    deps = AgentDeps(
        model=MockModelClient(script_for(task.scenario)),
        workspace=ws,
        registry=build_registry(ws),
        store=store,
        settings=SETTINGS,
    )

    return run_agent(run, deps)

@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    """PROVIDED. Returns a run and everything that happened during it."""
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run
