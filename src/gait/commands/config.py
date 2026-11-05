import click

from gait.core.state import StateManager


@click.group()
def config():
    """Read or update Gait configuration."""


@config.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    try:
        StateManager().set_config(key, value)
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Set {key} = {value}")


@config.command("get")
@click.argument("key")
def get_config(key: str) -> None:
    try:
        value = StateManager().get_config(key)
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    if value is None:
        raise click.ClickException(f"Config key is not set: {key}")
    click.echo(value)
