import sys
from collections import OrderedDict
import json
import click
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate

from faraday_cli.api_client import FaradayApi
from faraday_cli.config import active_config
from faraday_cli.cli import utils

HOST_CREATE_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "ip": {"type": "string"},
            "description": {"type": "string"},
            "hostnames": {"type": "array"},
        },
        "required": ['ip', 'description']
    }
}

@click.command(help="Host operations")
@click.option('-a', '--action', type=click.Choice(['list', 'get', 'delete', 'create'], case_sensitive=False),
              default="list", show_default=True)
@click.option('--json-output', is_flag=True, help="Output in json")
@click.option('-ws', '--workspace-name', type=str, help="Name of the workspace")
@click.option('-hid', '--host_id', type=int, help="id of the host")
@click.option('-d', '--host-data', type=str, help=f"json schema:{HOST_CREATE_JSON_SCHEMA}",
              callback=utils.json_schema_validator(HOST_CREATE_JSON_SCHEMA), required=False)
@click.option('--stdin', is_flag=True, help="Read host-data from stdin", show_default=True)
def host(action, json_output, workspace_name, host_id, host_data, stdin):
    api_client = FaradayApi(active_config.faraday_url, ssl_verify=active_config.ssl_verify,
                            session=active_config.session)

    if not workspace_name:
        workspace_name = active_config.workspace
    if not workspace_name:
        click.secho(f"Workspace is required", fg="red")
        return
    if not api_client.is_workspace_valid(workspace_name):
        click.secho(f"Invalid workspace: {workspace_name}", fg="red")

    def _list_hosts(workspace_name):
        hosts = api_client.get_hosts(workspace_name)
        data = [OrderedDict({'id': x['value']['id'],
                             'ip': x['value']['ip'],
                             'os': x['value']['os'],
                             'hostnames': ", ".join(x['value']['hostnames']),
                             'services': len(x['value']['service_summaries']),
                             'vulns': x['value']['vulns']}) for x in hosts['rows']]
        if json_output:
            click.echo(json.dumps(data, indent=4))
        else:

            click.secho(tabulate(data, headers="keys"), fg="yellow")

    def _get_host(workspace_name, host_id):
        try:
            host = api_client.get_host(workspace_name, host_id)
        except NotFoundError:
            click.secho("Host not found", fg="red")
            return
        if json_output:
            click.echo(json.dumps(host, indent=4))
        else:
            data = [OrderedDict({'id': x['id'],
                                 'ip': x['ip'],
                                 'os': x['os'],
                                 'hostnames': ", ".join(x['hostnames']),
                                 'owner': x['owner'],
                                 'owned': x['owned'],
                                 }) for x in [host]]
            services = api_client.get_host_services(workspace_name, host_id)
            services_data = [OrderedDict({'id': x['id'],
                                          'name': x['name'],
                                          'description': x['description'],
                                          'protocol': x['protocol'],
                                          'port': x['port'],
                                          'version': x['version'],
                                          'status': x['status'],
                                          'vulns': x['vulns'],
                                          }) for x in services]
            click.secho(tabulate(data, headers="keys"), fg="yellow")
            click.echo("\n")
            click.secho(tabulate(services_data, headers="keys"), fg="yellow")

    def _delete_host(workspace_name, host_id):
        try:
            hosts = api_client.delete_host(workspace_name, host_id)
        except NotFoundError:
            click.secho("Host not found", fg="red")
            return
        click.secho(f"Deleted host", fg="green")

    def _create_host(workspace_name, host_params):
        for _host_data in host_params:
            ip, hostname = utils.get_ip_and_hostname(_host_data['ip'])
            _host_data['ip'] = ip
            if hostname:
                if 'hostnames' in _host_data:
                    _host_data['hostnames'].append(hostname)
                else:
                    _host_data['hostnames'] = [hostname]
            try:
                host = api_client.create_host(workspace_name, _host_data)
            except Exception as e:
                click.secho(f"{e}", fg="red")
            else:
                click.secho(f"Created host\n{json.dumps(host, indent=4)}", fg="green")

    if action == "list":
        _list_hosts(workspace_name)

    elif action == 'get':
        if not host_id:
            click.secho("Host ID is required to get a host", fg="red")
        else:
            _get_host(workspace_name, host_id)

    elif action == 'delete':
        if not host_id:
            click.secho("Host ID is required to delete a host", fg="red")
        else:
            _delete_host(workspace_name, host_id)

    elif action == 'create':
        if not host_data and stdin:
            host_data = sys.stdin.read()
            host_data = utils.json_schema_validator(HOST_CREATE_JSON_SCHEMA)(None, None, host_data)
        if not host_data and not stdin:
            click.secho("Host params are required to create a host", fg="red")
        else:
            _create_host(workspace_name, host_data)




