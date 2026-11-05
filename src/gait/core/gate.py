from dataclasses import dataclass, field
from pathlib import Path
import subprocess

import yaml


@dataclass
class GateResult:
    passed: bool
    missing: list[str] = field(default_factory=list)


class GateExecutor:
    def __init__(self, project_root: str | Path, engine_path: str | Path | None = None):
        self.project_root = Path(project_root).resolve()
        self.engine_path = Path(engine_path).resolve() if engine_path else None

    def git_tracked_files_clean(self) -> bool | None:
        try:
            result = subprocess.run(
                ["git", "diff", "--quiet", "--", "."], cwd=self.project_root, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
        return None

    def run(self, gate_name: str, state: dict) -> GateResult:
        missing: list[str] = []
        stages = state.get("stages", {})
        if gate_name == "gate-design-artifacts":
            design = stages.get("requirement-design", {})
            paths = [design.get("design_doc", ""), *design.get("artifacts", {}).values()]
            for path in paths:
                if not path:
                    missing.append("artifact path is not configured")
                    continue
                target = self.project_root / path
                if path == design.get("artifacts", {}).get("spec") and target.is_dir():
                    if not any(target.rglob("*.md")):
                        missing.append(path)
                elif not target.is_file():
                    missing.append(path)
            clean = self.git_tracked_files_clean()
            if clean is False:
                missing.append("tracked business code has git changes")
            elif clean is None:
                missing.append("Unable to verify tracked file changes: project is not a usable Git repository")
        elif gate_name == "gate-code-test":
            coding = stages.get("coding", {})
            tasks_path = self.project_root / "openspec" / "changes" / state.get("openspec_change", "") / "tasks.md"
            if not tasks_path.is_file():
                missing.append(str(tasks_path.relative_to(self.project_root)))
            manifest_path = coding.get("manifest", "")
            full_manifest = self.project_root / manifest_path
            if not manifest_path or not full_manifest.is_file():
                missing.append(manifest_path or "coding manifest path is not configured")
            else:
                manifest = self._read_manifest(full_manifest)
                completed = set(coding.get("completed_task_ids", []))
                for task_id in self._task_ids(state):
                    if task_id not in completed:
                        missing.append(f"incomplete task_id: {task_id}")
                command = manifest.get("test_command")
                if not command:
                    missing.append("manifest.test_command is required")
                elif subprocess.run(command, cwd=self.project_root, shell=True, check=False).returncode != 0:
                    missing.append(f"test command failed: {command}")
        elif gate_name == "gate-close":
            closing = stages.get("closing", {})
            summary = closing.get("summary", "")
            if not summary or not (self.project_root / summary).is_file():
                missing.append(summary or "summary path is not configured")
            change = state.get("openspec_change", "")
            archive_dir = self.project_root / "openspec" / "changes" / "archive"
            archived = (archive_dir / change).exists() or any(archive_dir.glob(f"*{change}*")) if archive_dir.exists() else False
            if not archived:
                missing.append(f"OpenSpec change is not archived: {change}")
        else:
            raise ValueError(f"Unknown gate: {gate_name}")
        return GateResult(not missing, missing)

    def _task_ids(self, state: dict) -> list[str]:
        path = self.project_root / "openspec" / "changes" / state.get("openspec_change", "") / "tasks.md"
        if not path.is_file():
            return []
        import re

        content = path.read_text(encoding="utf-8")
        return re.findall(r"(?m)^\s*-\s*\[[ xX]\]\s+(\d+(?:\.\d+)*)\.", content)

    @staticmethod
    def _read_manifest(path: Path) -> dict:
        content = path.read_text(encoding="utf-8")
        try:
            value = yaml.safe_load(content)
            if isinstance(value, dict):
                return value
        except yaml.YAMLError:
            pass
        import re

        match = re.search(r"(?m)^\s*test_command\s*:\s*[`\"']?(.+?)[`\"']?\s*$", content)
        return {"test_command": match.group(1).strip() if match else None}
