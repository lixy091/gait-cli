import pytest

from gait.core import tool_bootstrap
from gait.core.tool_bootstrap import ensure_openspec_available


def test_skip_allows_init_but_later_openspec_operation_fails_with_install_hint(monkeypatch):
    monkeypatch.setattr("gait.core.tool_bootstrap.detect_tools", lambda: {"node": False, "npm": False, "openspec": False})

    with pytest.raises(RuntimeError, match="openspec.*install|install.*openspec"):
        ensure_openspec_available()


def test_check_mode_reports_missing_without_installing(monkeypatch, capsys):
    monkeypatch.setattr(tool_bootstrap, "detect_tools", lambda: {"node": True, "npm": True, "openspec": False})
    calls = []
    monkeypatch.setattr(tool_bootstrap, "run_streaming", lambda command, **kwargs: calls.append(command))

    result = tool_bootstrap.bootstrap_tools("check", interactive=True, platform_name="linux")

    assert result["openspec"] is False
    assert calls == []
    assert "npm install -g @fission-ai/openspec@latest" in capsys.readouterr().out


def test_install_mode_runs_openspec_installer_then_rechecks(monkeypatch):
    statuses = iter([
        {"node": True, "npm": True, "openspec": False},
        {"node": True, "npm": True, "openspec": True},
    ])
    calls = []
    monkeypatch.setattr(tool_bootstrap, "detect_tools", lambda: next(statuses))
    monkeypatch.setattr(tool_bootstrap, "run_streaming", lambda command, **kwargs: calls.append(command))
    monkeypatch.setattr(tool_bootstrap, "current_platform", lambda: "linux")

    result = tool_bootstrap.bootstrap_tools("install", interactive=True)

    assert result["openspec"] is True
    assert calls == ["npm install -g @fission-ai/openspec@latest"]


def test_auto_noninteractive_never_installs_and_reports_manual_commands(monkeypatch, capsys):
    monkeypatch.setattr(tool_bootstrap, "detect_tools", lambda: {"node": False, "npm": False, "openspec": False})
    calls = []
    monkeypatch.setattr(tool_bootstrap, "run_streaming", lambda command, **kwargs: calls.append(command))

    with pytest.raises(RuntimeError, match="gait init --tools install"):
        tool_bootstrap.bootstrap_tools("auto", interactive=False, platform_name="linux")
    assert calls == []
    assert "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh" in capsys.readouterr().out
