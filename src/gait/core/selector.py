from pathlib import Path

import yaml


class WorkflowSelector:
    def __init__(self, selector_path: str | Path):
        self.selector_path = Path(selector_path)

    def select(self, task_type: str) -> str:
        if not self.selector_path.is_file():
            raise FileNotFoundError(f"Workflow selector not found: {self.selector_path}")
        with self.selector_path.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        mappings = data.get("task_types", data.get("mapping", {}))
        try:
            return mappings[task_type]
        except KeyError as exc:
            raise ValueError(f"No workflow configured for task type: {task_type}") from exc
