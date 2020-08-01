import getpass
import click

from faraday_cli.config import active_config
from faraday_plugins.plugins.manager import PluginsManager, ReportAnalyzer

@click.command(help="Import vulns from tools reports")
@click.option('-cpf', '--custom-plugins-folder', type=str)
@click.option('--plugin_id', type=str)
@click.option('-ws', '--workspace', type=str)
@click.argument('filename', type=click.Path(exists=True))
@click.pass_obj
def report(api_client, custom_plugins_folder, plugin_id, workspace, filename):

    if workspace:
        if not api_client.is_workspace_valid(workspace):
            click.secho(f"Invalid workspace: {workspace}", fg="red")
            return
        else:
            destination_workspace = workspace
    else:
        if not active_config.workspace:
            click.secho(f"Missing default workspace", fg="red")
            return
        else:
            destination_workspace = active_config.workspace
    plugins_manager = PluginsManager(custom_plugins_folder)
    analyzer = ReportAnalyzer(plugins_manager)
    if plugin_id:
        plugin = plugins_manager.get_plugin(plugin_id)
        if not plugin:
            click.echo(click.style(f"Invalid Plugin: {plugin_id}", fg="red"), err=True)
            return
    else:
        plugin = analyzer.get_plugin(filename)
        if not plugin:
            click.echo(click.style(f"Failed to detect report: {filename}", fg="red"), err=True)
            return
    plugin.processReport(filename, getpass.getuser())
    click.secho(f"Sending data from {filename} to {destination_workspace}", fg="green")
    api_client.bulk_create(destination_workspace, plugin.get_data())






