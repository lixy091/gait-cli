import click

from gait.commands.config import config
from gait.commands.project import init
from gait.commands.task import task
from gait.commands.gate import gate


@click.group()
def cli():
    """Gait iterative workflow CLI."""


cli.add_command(init)
cli.add_command(config)
cli.add_command(task)
task.add_command(gate)


if __name__ == "__main__":
    cli()
