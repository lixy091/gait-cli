from pathlib import Path

import yaml


class StateManager:
    """The only supported writer for Gait project and task state."""

    CONFIG_KEYS = {"engine_path", "coding_agent"}

    def __init__(self, project_root: str | Path = "."):
        self.project_root = Path(project_root).resolve()
        self.gait_dir = self.project_root / ".gait"

    def initialize_project(self, engine_path: str, coding_agent: str) -> None:
        if coding_agent not in {"claude", "codex"}:
            raise ValueError("coding_agent must be claude or codex")
        self.gait_dir.mkdir(parents=True, exist_ok=True)
        self._write_yaml(
            self.gait_dir / "project.yaml",
            {"gait": {"engine_path": engine_path, "coding_agent": coding_agent}},
        )
        index_path = self.gait_dir / "tasks-index.yaml"
        if not index_path.exists():
            self._write_yaml(index_path, {"tasks": [], "active_task": None})

    def read_project(self) -> dict:
        return self._read_yaml(self.gait_dir / "project.yaml")

    def set_config(self, key: str, value: str) -> None:
        if key not in self.CONFIG_KEYS:
            raise ValueError(f"Unknown config key: {key}")
        data = self.read_project()
        data.setdefault("gait", {})[key] = value
        self._write_yaml(self.gait_dir / "project.yaml", data)

    def get_config(self, key: str):
        if key not in self.CONFIG_KEYS:
            raise ValueError(f"Unknown config key: {key}")
        return self.read_project().get("gait", {}).get(key)

    def read_task_state(self, task_id: str) -> dict:
        return self._read_yaml(self.gait_dir / "tasks" / task_id / "state.yaml")

    def write_task_state(self, task_id: str, state: dict) -> None:
        if state.get("task_id") != task_id:
            raise ValueError("task state task_id must match its directory")
        self._write_yaml(self.gait_dir / "tasks" / task_id / "state.yaml", state)

    def read_tasks_index(self) -> dict:
        return self._read_yaml(self.gait_dir / "tasks-index.yaml")

    def write_tasks_index(self, index: dict) -> None:
        self._write_yaml(self.gait_dir / "tasks-index.yaml", index)

    @staticmethod
    def _read_yaml(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        return value or {}

    @staticmethod
    def _write_yaml(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
