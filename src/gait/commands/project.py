from pathlib import Path

import click

from gait.core.state import StateManager
from gait.core.tool_bootstrap import bootstrap_tools, run_command


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


@click.command("init")
@click.option("--engine-path", default="../gait-engine", show_default=True)
@click.option("--tools", type=click.Choice(["auto", "check", "install", "skip"]), default="auto", show_default=True)
def init(engine_path: str, tools: str) -> None:
    """Initialize Gait in the current business project."""
    try:
        tool_status = bootstrap_tools(tools)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    coding_agent = click.prompt("Select coding runtime", type=click.Choice(["claude", "codex"]))
    manager = StateManager(Path.cwd())
    manager.initialize_project(engine_path=engine_path, coding_agent=coding_agent)
    template = TEMPLATES / ("CLAUDE.md.j2" if coding_agent == "claude" else "AGENTS.md.j2")
    destination = Path.cwd() / ("CLAUDE.md" if coding_agent == "claude" else "AGENTS.md")
    destination.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    if tools != "skip" and tool_status.get("openspec") and not (Path.cwd() / "openspec" / "config.yaml").exists():
        try:
            run_command(["openspec", "init"], cwd=Path.cwd())
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
    click.echo(f"Initialized Gait project at {manager.gait_dir}")
