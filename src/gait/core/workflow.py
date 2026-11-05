from pathlib import Path

import yaml


class WorkflowEngine:
    def __init__(self, engine_path: str | Path):
        self.engine_path = Path(engine_path).resolve()

    def load_workflow(self, name: str) -> dict:
        return self._load(self.engine_path / "workflows" / f"{name}.yaml")

    def load_stage(self, name: str) -> dict:
        return self._load(self.engine_path / "stages" / f"{name}.yaml")

    def load_gate(self, name: str) -> dict:
        return self._load(self.engine_path / "gates" / f"{name}.yaml")

    @staticmethod
    def _load(path: Path) -> dict:
        if not path.is_file():
            raise FileNotFoundError(f"Engine asset not found: {path}")
        with path.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        return data or {}
