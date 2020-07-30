#!/usr/bin/env python
import os
import click
from faraday_cli import __version__
from faraday_cli.config import active_config

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
@click.version_option(__version__, '-v', '--version')
def cli(ctx):
    if not os.path.isfile(active_config.config_file):
        if ctx.invoked_subcommand != "login":
            raise click.UsageError("Config file missing, run 'login' command first")
    else:
        active_config.load()


from .commands.workspace import workspace
from .commands.login import login
from .commands.report import report
from .commands.status import status
from .commands.command import command
from .commands.host import host

cli.add_command(login)
cli.add_command(workspace)
cli.add_command(report)
cli.add_command(status)
cli.add_command(command)
cli.add_command(host)

if __name__ == '__main__':
    cli()
