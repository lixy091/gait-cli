from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys

import click

from gait.core.selector import WorkflowSelector
from gait.core.gate import GateExecutor
from gait.core.state import StateManager
from gait.core.tool_bootstrap import ensure_openspec_available, run_command
from gait.core.workflow import WorkflowEngine


STAGES = ["requirement-design", "coding", "closing"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_state(manager: StateManager) -> dict:
    active = manager.read_tasks_index().get("active_task")
    if not active:
        raise click.ClickException("No active Gait task")
    return manager.read_task_state(active)


@click.group()
def task():
    """Manage the active Gait task."""


@task.command("init")
@click.option("--name", required=True)
@click.option("--type", "task_type", type=click.Choice(["feature", "bugfix"]), default="feature", show_default=True)
def task_init(name: str, task_type: str) -> None:
    manager = StateManager()
    project = manager.read_project().get("gait", {})
    engine_path = (manager.project_root / project.get("engine_path", "../gait-engine")).resolve()
    workflow = WorkflowSelector(engine_path / "selector.yaml").select(task_type)
    engine = WorkflowEngine(engine_path)
    workflow_data = engine.load_workflow(workflow)
    ensure_openspec_available()
    if not (manager.project_root / "openspec" / "config.yaml").exists():
        try:
            run_command(["openspec", "init"], cwd=manager.project_root)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

    index = manager.read_tasks_index()
    task_id = f"task-{len(index.get('tasks', [])) + 1:03d}"
    name_slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    change_id = f"{task_id}-{name_slug}" if name_slug else task_id
    capability = name_slug or task_id
    now = _now()
    state = {
        "task_id": task_id,
        "task_name": name,
        "task_type": task_type,
        "workflow": workflow,
        "current_stage": workflow_data["stages"][0],
        "openspec_change": change_id,
        "stages": {
            "requirement-design": {
                "design_doc": f"docs/requirement/{name}/需求设计文档.md",
                "artifacts": {
                    "spec": f"openspec/changes/{change_id}/specs/{capability}/spec.md",
                    "design": f"openspec/changes/{change_id}/design.md",
                    "tasks": f"openspec/changes/{change_id}/tasks.md",
                },
                "done": False,
            },
            "coding": {
                "completed_task_ids": [],
                "manifest": f"docs/{name}/coding-manifest.md",
                "unit_test_pass": False,
                "done": False,
            },
            "closing": {"archive_done": False, "summary": f"docs/{name}/summary.md", "done": False},
        },
        "ready_for_advance": False,
        "advances": [],
        "approvals": [],
        "status": "active",
        "created_at": now,
        "completed_at": None,
    }
    manager.write_task_state(task_id, state)
    index.setdefault("tasks", []).append({"task_id": task_id, "task_name": name, "status": "active"})
    index["active_task"] = task_id
    manager.write_tasks_index(index)
    try:
        run_command(["openspec", "new", "change", change_id], cwd=manager.project_root)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {task_id}; selected workflow {workflow}.")
    click.echo("Use the installed OpenSpec propose workflow to create proposal/spec/design/tasks artifacts.")


@task.command("status")
def task_status() -> None:
    manager = StateManager()
    state = _active_state(manager)
    stage = state["current_stage"]
    stage_state = state["stages"][stage]
    missing = []
    if stage == "requirement-design":
        if not (manager.project_root / stage_state["design_doc"]).exists():
            missing.append(stage_state["design_doc"])
        missing.extend(path for path in stage_state["artifacts"].values() if not (manager.project_root / path).exists())
    elif stage == "coding":
        if not (manager.project_root / stage_state["manifest"]).exists():
            missing.append(stage_state["manifest"])
    else:
        if not (manager.project_root / stage_state["summary"]).exists():
            missing.append(stage_state["summary"])
    click.echo(f"Task: {state['task_name']} ({state['task_id']})")
    click.echo(f"Stage: {stage}")
    click.echo("Missing: " + (", ".join(missing) if missing else "none"))
    click.echo("Next: " + (f"complete {stage} deliverables" if missing else "run gait task gate"))


@task.command("advance")
@click.option("--yes", is_flag=True, help="Confirm stage advance without an interactive prompt.")
def task_advance(yes: bool) -> None:
    manager = StateManager()
    state = _active_state(manager)
    stage = state["current_stage"]
    index = STAGES.index(stage)
    if index >= len(STAGES) - 1:
        raise click.ClickException("Closing is the final stage; use gait task close")
    project = manager.read_project().get("gait", {})
    engine = WorkflowEngine((manager.project_root / project.get("engine_path", "../gait-engine")).resolve())
    stage_data = engine.load_stage(stage)
    gate_name = stage_data.get("exit_gate") or stage_data.get("gate")
    result = GateExecutor(manager.project_root, engine.engine_path).run(gate_name, state)
    if not result.passed:
        raise click.ClickException("Gate failed:\n- " + "\n- ".join(result.missing))
    gate_data = engine.load_gate(gate_name)
    if gate_data.get("human_approval", False) and not any(item.get("gate") == gate_name for item in state.get("approvals", [])):
        raise click.ClickException(f"Gate {gate_name} requires explicit user approval via gait task gate --approve --approver NAME")
    state["ready_for_advance"] = True
    manager.write_task_state(state["task_id"], state)
    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException("Non-interactive advance requires --yes")
        if not click.confirm(f"Advance from {stage} to {STAGES[index + 1]}?", default=False):
            click.echo("Advance cancelled")
            return
    next_stage = STAGES[index + 1]
    state["advances"].append({"from": stage, "to": next_stage, "at": _now()})
    state["current_stage"] = next_stage
    state["ready_for_advance"] = False
    state["stages"][stage]["done"] = True
    manager.write_task_state(state["task_id"], state)
    click.echo(f"Advanced to {next_stage}")


@task.command("rollback")
@click.option("--reason", required=True)
def task_rollback(reason: str) -> None:
    manager = StateManager()
    state = _active_state(manager)
    index = STAGES.index(state["current_stage"])
    if index == 0:
        raise click.ClickException("Already at the first stage")
    previous = STAGES[index - 1]
    trash = manager.gait_dir / "trash" / state["task_id"] / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{state['current_stage']}"
    trash.mkdir(parents=True, exist_ok=True)
    current = state["stages"].get(state["current_stage"], {})
    candidates = [current.get("manifest"), current.get("summary"), *current.get("artifacts", {}).values()]
    for relative in filter(None, candidates):
        source = manager.project_root / relative
        if source.is_file():
            destination = trash / relative.replace("/", "__")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
    state["current_stage"] = previous
    state["ready_for_advance"] = False
    state["advances"].append({"from": STAGES[index], "to": previous, "at": _now(), "reason": reason, "rollback": True})
    manager.write_task_state(state["task_id"], state)
    click.echo(f"Rolled back to {previous}; archived artifacts in {trash}")


@task.command("complete")
@click.option("--task-id", "completed_id", required=True, help="Task ID from OpenSpec tasks.md.")
def task_complete(completed_id: str) -> None:
    """Run the coding manifest test command and record a completed task ID."""
    manager = StateManager()
    state = _active_state(manager)
    if state["current_stage"] != "coding":
        raise click.ClickException("Task IDs can only be completed during coding")
    coding = state["stages"]["coding"]
    manifest_path = manager.project_root / coding["manifest"]
    if not manifest_path.is_file():
        raise click.ClickException(f"Coding manifest not found: {manifest_path}")
    manifest = GateExecutor._read_manifest(manifest_path)
    command = manifest.get("test_command")
    if not command:
        raise click.ClickException("coding manifest must define test_command")
    if completed_id not in GateExecutor(manager.project_root)._task_ids(state):
        raise click.ClickException(f"Task ID {completed_id} does not exist in OpenSpec tasks.md")
    result = subprocess.run(command, cwd=manager.project_root, shell=True, check=False)
    if result.returncode:
        raise click.ClickException(f"Test command failed ({result.returncode}); task ID was not recorded")
    if completed_id not in coding.setdefault("completed_task_ids", []):
        coding["completed_task_ids"].append(completed_id)
    coding["unit_test_pass"] = True
    manager.write_task_state(state["task_id"], state)
    click.echo(f"Tests passed; recorded task ID {completed_id}")


@task.command("close")
def task_close() -> None:
    manager = StateManager()
    state = _active_state(manager)
    if state["current_stage"] != "closing":
        raise click.ClickException("Task can only be closed from the closing stage")
    ensure_openspec_available()
    project = manager.read_project().get("gait", {})
    engine = WorkflowEngine((manager.project_root / project.get("engine_path", "../gait-engine")).resolve())
    close_gate = engine.load_stage("closing").get("exit_gate")
    summary_path = manager.project_root / state["stages"]["closing"]["summary"]
    if not summary_path.is_file():
        raise click.ClickException(f"Summary is required before archive: {summary_path}")
    try:
        run_command(["openspec", "archive", state["openspec_change"], "--yes"], cwd=manager.project_root)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    result = GateExecutor(manager.project_root, engine.engine_path).run(close_gate, state)
    if not result.passed:
        raise click.ClickException("Close gate failed:\n- " + "\n- ".join(result.missing))
    state["stages"]["closing"]["archive_done"] = True
    state["stages"]["closing"]["done"] = True
    state["status"] = "completed"
    state["completed_at"] = _now()
    manager.write_task_state(state["task_id"], state)
    index = manager.read_tasks_index()
    for item in index.get("tasks", []):
        if item.get("task_id") == state["task_id"]:
            item["status"] = "completed"
    index["active_task"] = None
    manager.write_tasks_index(index)
    click.echo(f"Closed {state['task_id']}")
