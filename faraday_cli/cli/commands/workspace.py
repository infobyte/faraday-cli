import json
from collections import OrderedDict
import click
from tabulate import tabulate

from faraday_cli.config import active_config


@click.command(help="Workspace operations")
@click.option('-a', '--action', type=click.Choice(['list', 'create', 'delete', 'select'], case_sensitive=False),
              default="list", show_default=True)
@click.option('--json-output', is_flag=True, help="Output in json")
@click.option('-n', '--name', type=str, help="Name of the workspace")
@click.pass_obj
def workspace(api_client, action, json_output, name):

    def _list_workspaces():
        workspaces = api_client.get_workspaces()
        if not workspaces:
            click.secho("No workspaces available", fg="yellow")
            return
        data = [OrderedDict({'name': x['name'],
                                          'hosts': x['stats']['hosts'],
                                          'services': x['stats']['services'],
                                          'vulns': x['stats']['total_vulns']
                                          }) for x in workspaces]
        if json_output:
            click.echo(json.dumps(data, indent=4))
        else:
            click.secho(tabulate(data, headers="keys"), fg="yellow")

    def _create_workspace(workspace_name):
        try:
            created_workspace = api_client.create_workspace(workspace_name)
        except Exception as e:
            click.secho(f"{e}", fg="red")
        else:
            click.secho(f"Created workspace: {workspace_name}", fg="green")

    def _select_workspace(selected_workspace):
        workspaces = api_client.get_workspaces()
        workspace_choices = [ws for ws in map(lambda x: x['name'], workspaces)]
        if not selected_workspace:
            selected_workspace = click.prompt(
                f"Select workspace",
                type=click.Choice(choices=workspace_choices, case_sensitive=False),
            )
        else:
            if selected_workspace not in workspace_choices:
                click.secho(f"Invalid worskpace: {selected_workspace}", fg="red")
                return
        click.secho(f"Selected Workspace: {selected_workspace}", fg="green")
        active_config.workspace = selected_workspace
        active_config.save()

    def _delete_workspace(workspace_to_delete):
        workspaces = api_client.get_workspaces()
        workspace_choices = [ws for ws in map(lambda x: x['name'], workspaces)]
        if not workspace_to_delete:
            workspace_to_delete = click.prompt(
                f"Select workspace",
                type=click.Choice(choices=workspace_choices, case_sensitive=False),
            )
        else:
            if workspace_to_delete not in workspace_choices:
                click.secho(f"Invalid worskpace: {workspace_to_delete}", fg="red")
                return
        response = api_client.delete_workspace(workspace_to_delete)
        click.secho(f"Deleted workspace: {workspace_to_delete}", fg="green")
        if active_config.workspace == workspace_to_delete:
            active_config.workspace = None
            active_config.save()

    if action == "list":
        _list_workspaces()

    elif action == 'create':
        if not name:
            click.secho("Name is required to create a workspace", fg="red")
        else:
            _create_workspace(name)

    elif action == 'select':
        _select_workspace(name)

    elif action == 'delete':
        _delete_workspace(name)
