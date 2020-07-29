from collections import OrderedDict
import json
import click
from tabulate import tabulate

from faraday_cli.api_client import FaradayApi
from faraday_cli.config import active_config


@click.command(help="Host operations")
@click.option('-a', '--action', type=click.Choice(['list', 'create', 'delete'], case_sensitive=False),
              default="list", show_default=True)
@click.option('--json-output', is_flag=True, help="Output in json")
@click.option('-n', '--name', type=str, help="Name of the host")
@click.option('-ws', '--workspace', type=str)
def host(action, json_output, name, workspace):
    api_client = FaradayApi(active_config.faraday_url, ssl_verify=active_config.ssl_verify,
                            session=active_config.session)

    def _list_hosts(workspace_name):
        if not api_client.is_workspace_valid(workspace_name):
            click.secho(f"Invalid workspace: {workspace_name}", fg="red")
        hosts = api_client.get_hosts(workspace_name)
        data = [OrderedDict({'name': x['value']['name'],
                             'ip': x['value']['ip'],
                             'os': x['value']['os'],
                             'hostnames': " ".join(x['value']['hostnames']),
                             'services': len(x['value']['service_summaries']),
                             'vulns': x['value']['vulns']}) for x in hosts['rows']]
        if json_output:
            click.echo(json.dumps(data, indent=4))
        else:

            click.secho(tabulate(data, headers="keys"), fg="yellow")

    def _create_host(host_name):
        created_host = api_client.create_host(host_name)
        click.secho(f"Created host: {created_host['name']}", fg="green")

    def _delete_host(host_to_delete):
        hosts = api_client.get_hosts()
        host_choices = [ws for ws in map(lambda x: x['name'], hosts)]
        if not host_to_delete:
            host_to_delete = click.prompt(
                f"Select host",
                type=click.Choice(choices=host_choices, case_sensitive=False),
            )
        else:
            if host_to_delete not in host_choices:
                click.secho(f"Invalid worskpace: {host_to_delete}", fg="red")
                return
        response = api_client.delete_host(host_to_delete)
        click.secho(f"Deleted host: {host_to_delete}", fg="green")

    if action == "list":
        if not workspace:
            workspace = active_config.workspace
        if not workspace:
            click.secho(f"Workspace is required", fg="red")
            return
        _list_hosts(workspace)

    elif action == 'create':
        if not name:
            click.secho("Name is required to create a host", fg="red")
        else:
            _create_host(name)

    elif action == 'delete':
        _delete_host(name)



