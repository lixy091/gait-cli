import click

from gait.commands.task import _active_state, _now
from gait.core.gate import GateExecutor
from gait.core.state import StateManager
from gait.core.workflow import WorkflowEngine


@click.command("gate")
@click.option("--approve", is_flag=True, help="Record explicit user approval after checks pass.")
@click.option("--approver", default="")
@click.option("--comment", default="")
def gate(approve: bool, approver: str, comment: str) -> None:
    """Run the current stage exit gate. AI must not self-approve."""
    manager = StateManager()
    state = _active_state(manager)
    project = manager.read_project().get("gait", {})
    engine = WorkflowEngine((manager.project_root / project.get("engine_path", "../gait-engine")).resolve())
    gate_name = engine.load_stage(state["current_stage"]).get("exit_gate")
    result = GateExecutor(manager.project_root, engine.engine_path).run(gate_name, state)
    if not result.passed:
        click.echo("Gate failed:\n- " + "\n- ".join(result.missing))
        return
    click.echo(f"Gate passed: {gate_name}")
    gate_requires_approval = engine.load_gate(gate_name).get("human_approval", False)
    if approve:
        if not approver:
            raise click.ClickException("--approver is required with --approve")
        state.setdefault("approvals", []).append({"gate": gate_name, "approver": approver, "comment": comment, "at": _now()})
        state["ready_for_advance"] = True
        manager.write_task_state(state["task_id"], state)
        click.echo(f"Approval recorded for {gate_name} by {approver}")
    else:
        click.echo("No approval recorded. Only the user may approve explicitly with --approve.")
        if gate_requires_approval:
            click.echo("This gate requires explicit user approval before advance.")
