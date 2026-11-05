from click.testing import CliRunner

from gait.cli import cli
from gait.core.state import StateManager


def setup_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = tmp_path / "engine"
    for folder in ("workflows", "stages", "gates"):
        (engine / folder).mkdir(parents=True, exist_ok=True)
    (engine / "selector.yaml").write_text("task_types:\n  feature: normal-iteration\n", encoding="utf-8")
    (engine / "workflows/normal-iteration.yaml").write_text("stages: [requirement-design, coding, closing]\n", encoding="utf-8")
    for stage, gate in (("requirement-design", "gate-design-artifacts"), ("coding", "gate-code-test"), ("closing", "gate-close")):
        (engine / f"stages/{stage}.yaml").write_text(f"name: {stage}\nexit_gate: {gate}\n", encoding="utf-8")
        (engine / f"gates/{gate}.yaml").write_text(f"name: {gate}\nhuman_approval: true\nchecks: []\n", encoding="utf-8")
    runner = CliRunner()
    runner.invoke(cli, ["init", "--engine-path", str(engine), "--tools", "skip"], input="codex\n")
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)
    monkeypatch.setattr("gait.commands.task.run_command", lambda *args, **kwargs: None)
    runner.invoke(cli, ["task", "init", "--name", "sample"])
    return runner, StateManager(tmp_path)


def test_advance_requires_gate_and_confirmation_then_records_transition(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    state = manager.read_task_state("task-001")
    state["ready_for_advance"] = True
    manager.write_task_state("task-001", state)
    monkeypatch.setattr("gait.commands.task.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    monkeypatch.setattr("gait.commands.gate.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Human"])

    result = runner.invoke(cli, ["task", "advance", "--yes"])

    assert result.exit_code == 0, result.output
    updated = manager.read_task_state("task-001")
    assert updated["current_stage"] == "coding"
    assert updated["advances"][0]["from"] == "requirement-design"


def test_advance_without_yes_is_blocked_in_noninteractive_runner(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    state = manager.read_task_state("task-001")
    state["ready_for_advance"] = True
    manager.write_task_state("task-001", state)
    monkeypatch.setattr("gait.commands.task.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    monkeypatch.setattr("gait.commands.gate.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Human"])

    result = runner.invoke(cli, ["task", "advance"], input="y\n")

    assert result.exit_code != 0
    assert "requires --yes" in result.output
    assert manager.read_task_state("task-001")["current_stage"] == "requirement-design"


def test_gate_approval_is_explicit_user_action(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    monkeypatch.setattr("gait.commands.task.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())

    result = runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Lin", "--comment", "reviewed"])

    assert result.exit_code == 0, result.output
    approval = manager.read_task_state("task-001")["approvals"][0]
    assert approval["approver"] == "Lin"
    assert approval["comment"] == "reviewed"


def test_close_archives_openspec_change_and_marks_task_completed(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    state = manager.read_task_state("task-001")
    state["current_stage"] = "closing"
    manager.write_task_state("task-001", state)
    summary = tmp_path / state["stages"]["closing"]["summary"]
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("done", encoding="utf-8")
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)
    monkeypatch.setattr("gait.commands.task.run_command", lambda args, **kwargs: (tmp_path / "openspec/changes/archive/task-001").mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr("gait.commands.task.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    monkeypatch.setattr("gait.commands.gate.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Human"])

    result = runner.invoke(cli, ["task", "close"])

    assert result.exit_code == 0, result.output
    assert manager.read_task_state("task-001")["status"] == "completed"


def test_close_requires_summary_and_archive_gate(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    state = manager.read_task_state("task-001")
    state["current_stage"] = "closing"
    manager.write_task_state("task-001", state)
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)
    monkeypatch.setattr("gait.commands.task.run_command", lambda *args, **kwargs: None)

    result = runner.invoke(cli, ["task", "close"])

    assert result.exit_code != 0
    assert manager.read_task_state("task-001")["status"] == "active"


def test_task_complete_runs_manifest_test_before_state_write(tmp_path, monkeypatch):
    runner, manager = setup_task(tmp_path, monkeypatch)
    state = manager.read_task_state("task-001")
    state["current_stage"] = "coding"
    manifest = tmp_path / state["stages"]["coding"]["manifest"]
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('test_command: "pytest -q"\n', encoding="utf-8")
    tasks = tmp_path / "openspec/changes" / state["openspec_change"] / "tasks.md"
    tasks.parent.mkdir(parents=True, exist_ok=True)
    tasks.write_text("- [ ] 1. Task\n", encoding="utf-8")
    manager.write_task_state("task-001", state)
    monkeypatch.setattr("gait.commands.task.subprocess.run", lambda *args, **kwargs: type("R", (), {"returncode": 0})())

    result = runner.invoke(cli, ["task", "complete", "--task-id", "1"])

    assert result.exit_code == 0, result.output
    assert "1" in manager.read_task_state("task-001")["stages"]["coding"]["completed_task_ids"]
