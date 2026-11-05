from gait.core.state import StateManager


def test_project_config_round_trip_and_task_state(tmp_path):
    manager = StateManager(tmp_path)
    manager.initialize_project(engine_path="../gait-engine", coding_agent="codex")

    project = manager.read_project()
    assert project == {"gait": {"engine_path": "../gait-engine", "coding_agent": "codex"}}

    manager.write_task_state("task-1", {"task_id": "task-1", "status": "active"})
    assert manager.read_task_state("task-1") == {"task_id": "task-1", "status": "active"}


def test_update_project_config_writes_only_through_manager(tmp_path):
    manager = StateManager(tmp_path)
    manager.initialize_project(engine_path="engine", coding_agent="claude")

    manager.set_config("engine_path", "../engine-v2")

    assert manager.get_config("engine_path") == "../engine-v2"
    assert manager.get_config("coding_agent") == "claude"


def test_unknown_config_key_is_rejected(tmp_path):
    manager = StateManager(tmp_path)
    manager.initialize_project(engine_path="engine", coding_agent="claude")

    try:
        manager.set_config("unknown", "value")
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("unknown config key should be rejected")
