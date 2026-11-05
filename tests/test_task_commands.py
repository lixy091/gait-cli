from click.testing import CliRunner

from gait.cli import cli


def test_task_init_creates_state_selects_workflow_and_creates_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = tmp_path / "engine"
    (engine / "workflows").mkdir(parents=True)
    (engine / "workflows" / "normal-iteration.yaml").write_text("name: normal-iteration\nstages: [requirement-design, coding, closing]\n", encoding="utf-8")
    (engine / "selector.yaml").write_text("task_types:\n  feature: normal-iteration\n  bugfix: normal-iteration\n", encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--engine-path", str(engine), "--tools", "skip"], input="codex\n").exit_code == 0
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)
    calls = []
    monkeypatch.setattr("gait.commands.task.run_command", lambda args, **kwargs: calls.append(args))

    result = runner.invoke(cli, ["task", "init", "--name", "new-feature", "--type", "feature"])

    assert result.exit_code == 0, result.output
    state = __import__("yaml").safe_load((tmp_path / ".gait/tasks/task-001/state.yaml").read_text(encoding="utf-8"))
    assert state["workflow"] == "normal-iteration"
    assert state["current_stage"] == "requirement-design"
    assert state["openspec_change"] == "task-001-new-feature"
    assert calls == [["openspec", "init"], ["openspec", "new", "change", "task-001-new-feature"]]
    index = __import__("yaml").safe_load((tmp_path / ".gait/tasks-index.yaml").read_text(encoding="utf-8"))
    assert index["active_task"] == "task-001"


def test_task_status_reports_current_stage_and_missing_work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = tmp_path / "engine"
    (engine / "workflows").mkdir(parents=True)
    (engine / "workflows" / "normal-iteration.yaml").write_text("name: normal-iteration\nstages: [requirement-design, coding, closing]\n", encoding="utf-8")
    (engine / "selector.yaml").write_text("task_types:\n  feature: normal-iteration\n", encoding="utf-8")
    runner = CliRunner()
    runner.invoke(cli, ["init", "--engine-path", str(engine), "--tools", "skip"], input="claude\n")
    monkeypatch.setattr("gait.commands.task.ensure_openspec_available", lambda: None)
    monkeypatch.setattr("gait.commands.task.run_command", lambda *args, **kwargs: None)
    runner.invoke(cli, ["task", "init", "--name", "login"])

    result = runner.invoke(cli, ["task", "status"])

    assert result.exit_code == 0, result.output
    assert "requirement-design" in result.output
    assert "docs/requirement/login" in result.output
