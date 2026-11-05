from gait.core.gate import GateExecutor


def test_design_gate_checks_artifacts_and_git_clean(tmp_path, monkeypatch):
    task = {
        "task_name": "sample",
        "openspec_change": "task-001-sample",
        "stages": {"requirement-design": {
            "design_doc": "docs/requirement/sample/需求设计文档.md",
            "artifacts": {name: f"openspec/changes/task-001-sample/artifacts/{name}.md" for name in ("spec", "design", "tasks")},
        }},
    }
    for relative in [task["stages"]["requirement-design"]["design_doc"], *task["stages"]["requirement-design"]["artifacts"].values()]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")
    executor = GateExecutor(tmp_path)
    monkeypatch.setattr(executor, "git_tracked_files_clean", lambda: True)

    result = executor.run("gate-design-artifacts", task)

    assert result.passed
    assert result.missing == []


def test_non_git_project_fails_design_gate_with_explanation(tmp_path, monkeypatch):
    executor = GateExecutor(tmp_path)
    monkeypatch.setattr(executor, "git_tracked_files_clean", lambda: None)

    result = executor.run("gate-design-artifacts", {"stages": {"requirement-design": {"design_doc": "missing", "artifacts": {}}}})

    assert not result.passed
    assert any("Git" in item for item in result.missing)


def test_task_parser_recognizes_open_spec_checkbox_task_ids(tmp_path):
    executor = GateExecutor(tmp_path)
    change_dir = tmp_path / "openspec/changes/c1"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text("- [ ] 1. Parent task\n  - [x] 1.1. Child task\n", encoding="utf-8")

    assert executor._task_ids({"openspec_change": "c1"}) == ["1", "1.1"]
