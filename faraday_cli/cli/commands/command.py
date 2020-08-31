import io
import os
import subprocess
import sys
import getpass
import shlex
import click

from faraday_cli.config import active_config
from faraday_plugins.plugins.manager import PluginsManager, CommandAnalyzer


@click.command(help="Import vulns from command")
@click.option("-cpf", "--custom-plugins-folder", type=str)
@click.option("--plugin_id", type=str)
@click.option("-ws", "--workspace", type=str)
@click.option("--hide-output", is_flag=True, show_default=True)
@click.argument("command", type=str)
@click.pass_obj
def command(
    api_client,
    custom_plugins_folder,
    plugin_id,
    workspace,
    hide_output,
    command,
):

    if workspace:
        if not api_client.is_workspace_valid(workspace):
            click.secho(f"Invalid workspace: {workspace}", fg="red")
            return
        else:
            destination_workspace = workspace
    else:
        if not active_config.workspace:
            click.secho("Missing default workspace", fg="red")
            return
        else:
            destination_workspace = active_config.workspace
    plugins_manager = PluginsManager(custom_plugins_folder)
    analyzer = CommandAnalyzer(plugins_manager)
    if plugin_id:
        plugin = plugins_manager.get_plugin(plugin_id)
        if not plugin:
            click.echo(
                click.style(f"Invalid Plugin: {plugin_id}", fg="red"), err=True
            )
            return
    else:
        plugin = analyzer.get_plugin(command)
        if not plugin:
            click.echo(
                click.style(f"Failed to detect command: {command}", fg="red"),
                err=True,
            )
            return
    current_path = os.path.abspath(os.getcwd())
    modified_command = plugin.processCommandString(
        getpass.getuser(), current_path, command
    )
    if modified_command:
        command = modified_command
    p = subprocess.Popen(
        shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    output = io.StringIO()
    while True:
        retcode = p.poll()
        line = p.stdout.readline().decode("utf-8")
        if not hide_output:
            sys.stdout.write(line)
        output.write(line)
        if retcode is not None:
            extra_lines = map(
                lambda x: x.decode("utf-8"), p.stdout.readlines()
            )
            if not hide_output:
                sys.stdout.writelines(line)
            output.writelines(extra_lines)
            break
    output_value = output.getvalue()
    if retcode == 0:
        plugin.processOutput(output_value)
        message = (
            f"Sending data from command [{command}] "
            f"to workspace: {destination_workspace}"
        )
        click.secho(message, fg="green")
        api_client.bulk_create(destination_workspace, plugin.get_data())
    else:
        click.secho("Command execution error!!", fg="red")
