from pathlib import Path

from click.testing import CliRunner
import yaml

from gait.cli import cli


def test_init_creates_project_config_and_runtime_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gait.core.tool_bootstrap.detect_tools", lambda: {"node": True, "npm": True, "openspec": True})
    calls = []
    monkeypatch.setattr("gait.commands.project.run_command", lambda args, **kwargs: calls.append((args, kwargs)))
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["init", "--engine-path", "../gait-engine", "--tools", "check"],
        input="codex\n",
        env={"CI": "1"},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".gait" / "project.yaml").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert "engine_path: ../gait-engine" in (tmp_path / ".gait" / "project.yaml").read_text()
    assert "coding_agent: codex" in (tmp_path / ".gait" / "project.yaml").read_text()
    agents_instructions = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "一次只问一个澄清问题" in agents_instructions
    assert "得到用户明确确认之前，不得创建需求设计文档或 OpenSpec artifacts" in agents_instructions
    assert calls and calls[0][0] == ["openspec", "init"]


def test_init_tools_check_reports_missing_without_install(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gait.core.tool_bootstrap.detect_tools", lambda: {"node": False, "npm": False, "openspec": False})
    runner = CliRunner()

    result = runner.invoke(cli, ["init", "--tools", "check"], input="claude\n", catch_exceptions=False)

    assert result.exit_code == 0
    assert "node" in result.output.lower()
    assert "openspec" in result.output.lower()
    assert not (tmp_path / ".gait").exists() or (tmp_path / ".gait" / "project.yaml").exists()


def test_config_set_and_get(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    initialized = runner.invoke(cli, ["init", "--tools", "skip"], input="claude\n", catch_exceptions=False)
    assert initialized.exit_code == 0, initialized.output

    set_result = runner.invoke(cli, ["config", "set", "engine_path", "../engine"], catch_exceptions=False)
    get_result = runner.invoke(cli, ["config", "get", "engine_path"], catch_exceptions=False)

    assert set_result.exit_code == 0, set_result.output
    assert get_result.exit_code == 0, get_result.output
    assert "../engine" in get_result.output


def test_requirement_design_stage_requires_confirmation_before_artifacts():
    stage_path = Path(__file__).resolve().parents[2] / "gait-engine" / "stages" / "requirement-design.yaml"
    stage = yaml.safe_load(stage_path.read_text(encoding="utf-8"))

    assert "一次只问一个澄清问题" in stage["instructions"]
    assert "得到用户明确确认之前，不得创建需求设计文档或 OpenSpec artifacts" in stage["instructions"]
