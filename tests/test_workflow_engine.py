from gait.core.selector import WorkflowSelector
from gait.core.workflow import WorkflowEngine


def test_engine_loads_workflow_and_referenced_stage(tmp_path):
    (tmp_path / "workflows").mkdir()
    (tmp_path / "stages").mkdir()
    (tmp_path / "workflows" / "normal-iteration.yaml").write_text(
        "name: normal-iteration\nstages: [requirement-design, coding, closing]\n", encoding="utf-8"
    )
    (tmp_path / "stages" / "requirement-design.yaml").write_text(
        "name: requirement-design\nallow_code_modification: false\nexit_gate: gate-design-artifacts\n", encoding="utf-8"
    )
    engine = WorkflowEngine(tmp_path)

    assert engine.load_workflow("normal-iteration")["stages"][0] == "requirement-design"
    assert engine.load_stage("requirement-design")["allow_code_modification"] is False


def test_selector_maps_feature_and_bugfix(tmp_path):
    selector_file = tmp_path / "selector.yaml"
    selector_file.write_text("task_types:\n  feature: normal-iteration\n  bugfix: normal-iteration\n", encoding="utf-8")
    selector = WorkflowSelector(selector_file)

    assert selector.select("feature") == "normal-iteration"
    assert selector.select("bugfix") == "normal-iteration"
