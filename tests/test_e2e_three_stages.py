from click.testing import CliRunner

from gait.cli import cli
from gait.core.state import StateManager


def write_engine(path):
    for directory in ("workflows", "stages", "gates", "contexts"):
        (path / directory).mkdir(parents=True, exist_ok=True)
    (path / "selector.yaml").write_text("task_types:\n  feature: normal-iteration\n  bugfix: normal-iteration\n", encoding="utf-8")
    (path / "workflows/normal-iteration.yaml").write_text(
        "name: normal-iteration\nstages: [requirement-design, coding, closing]\n", encoding="utf-8"
    )
    for stage, gate in (("requirement-design", "gate-design-artifacts"), ("coding", "gate-code-test"), ("closing", "gate-close")):
        (path / f"stages/{stage}.yaml").write_text(f"name: {stage}\nexit_gate: {gate}\n", encoding="utf-8")
        (path / f"gates/{gate}.yaml").write_text(f"name: {gate}\nhuman_approval: true\nchecks: []\n", encoding="utf-8")


def test_e2e_init_task_design_code_close(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = tmp_path / "engine"
    write_engine(engine)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--engine-path", str(engine), "--tools", "skip"], input="codex\n").exit_code == 0
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)

    def fake_openspec(args, cwd=None, check=None, **kwargs):
        if isinstance(args, str):
            return type("Completed", (), {"returncode": 0})()
        if args[1:3] == ["new", "change"]:
            artifacts = tmp_path / "openspec/changes" / args[3] / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
        elif args[1] == "archive":
            source = tmp_path / "openspec/changes" / args[2]
            archive = tmp_path / "openspec/changes/archive" / args[2]
            archive.parent.mkdir(parents=True, exist_ok=True)
            source.rename(archive)

    monkeypatch.setattr("gait.commands.task.run_command", lambda args, **kwargs: fake_openspec(args, **kwargs))
    created = runner.invoke(cli, ["task", "init", "--name", "demo"])
    assert created.exit_code == 0, created.output
    manager = StateManager(tmp_path)
    state = manager.read_task_state("task-001")
    design_doc = tmp_path / state["stages"]["requirement-design"]["design_doc"]
    design_doc.parent.mkdir(parents=True, exist_ok=True)
    design_doc.write_text("设计", encoding="utf-8")
    for relative in state["stages"]["requirement-design"]["artifacts"].values():
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# artifact", encoding="utf-8")
    monkeypatch.setattr("gait.core.gate.GateExecutor.git_tracked_files_clean", lambda self: True)
    monkeypatch.setattr("gait.commands.gate.GateExecutor.run", lambda *args, **kwargs: type("R", (), {"passed": True, "missing": []})())
    approved = runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Demo User"])
    assert approved.exit_code == 0, approved.output
    advanced = runner.invoke(cli, ["task", "advance", "--yes"])
    assert advanced.exit_code == 0, advanced.output

    state = manager.read_task_state("task-001")
    tasks_file = tmp_path / state["stages"]["requirement-design"]["artifacts"]["tasks"]
    tasks_file.write_text("- [ ] 1. Implement demo\n", encoding="utf-8")
    coding = state["stages"]["coding"]
    manifest = tmp_path / coding["manifest"]
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("test_command: python -c pass\n", encoding="utf-8")
    completed = runner.invoke(cli, ["task", "complete", "--task-id", "1"])
    assert completed.exit_code == 0, completed.output
    approved = runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Demo User"])
    assert approved.exit_code == 0, approved.output
    advanced = runner.invoke(cli, ["task", "advance", "--yes"])
    assert advanced.exit_code == 0, advanced.output

    state = manager.read_task_state("task-001")
    summary = tmp_path / state["stages"]["closing"]["summary"]
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("完成", encoding="utf-8")
    approved = runner.invoke(cli, ["task", "gate", "--approve", "--approver", "Demo User"])
    assert approved.exit_code == 0, approved.output
    closed = runner.invoke(cli, ["task", "close"])
    assert closed.exit_code == 0, closed.output
    assert manager.read_task_state("task-001")["status"] == "completed"
