from collections import OrderedDict
import json
import click
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate

from faraday_cli.api_client import FaradayApi
from faraday_cli.config import active_config


@click.command(help="Agent operations")
@click.option('-a', '--action', type=click.Choice(['list', 'get', 'run'], case_sensitive=False),
              default="list", show_default=True)
@click.option('-ws', '--workspace-name', type=str, help="Workspace name")
@click.option('-ag', '--agent_id', type=int, help="Agent ID")
@click.option('-e', '--executor_id', type=int, help="Executor ID")
@click.option('-p', '--executor-params', type=str, help="Executor Params in json")
def agent(action, workspace_name, agent_id, executor_id, executor_params):
    api_client = FaradayApi(active_config.faraday_url, ssl_verify=active_config.ssl_verify,
                            session=active_config.session)

    if not workspace_name:
        workspace_name = active_config.workspace
    if not workspace_name:
        click.secho(f"Workspace is required", fg="red")
        return
    if not api_client.is_workspace_valid(workspace_name):
        click.secho(f"Invalid workspace: {workspace_name}", fg="red")

    def _list_agents(workspace_name):
        agents = api_client.get_workspace_agents(workspace_name)
        data = [OrderedDict({'id': x['id'],
                             'name': x['name'],
                             'active': x['active'],
                             'status': x['status'],
                             'executors': " ".join([i['name'] for i in x['executors']])
                             }) for x in agents]
        click.secho(tabulate(data, headers="keys"), fg="yellow")

    def _get_agent(workspace_name, agent_id):
        try:
            agent = api_client.get_agent(workspace_name, agent_id)
        except NotFoundError:
            click.secho("Host not found", fg="red")
            return
        data = [OrderedDict({'id': x['id'],
                             'name': x['name'],
                             'active': x['active'],
                             'status': x['status']
                             }) for x in [agent]]
        executors_data = [OrderedDict({'id': x['id'],
                                       'name': x['name'],
                                       'parameters': ", ".join([i for i in x['parameters_metadata'].keys()])
                                       }) for x in agent['executors']]
        click.secho(tabulate(data, headers="keys"), fg="yellow")
        click.secho("\nExecutors:", fg="yellow")
        click.secho(tabulate(executors_data, headers="keys"), fg="yellow")

    def _run_executor(workspace_name, agent_id, executor_id, executor_params):
        try:
            executor_params = json.loads(executor_params)
        except Exception:
            click.secho(f"Invalid Executor params format [{executor_params}]", fg="red")
            return
        agent = api_client.get_agent(workspace_name, agent_id)
        executor = None
        for executor in agent['executors']:
            if executor['id'] == executor_id:
                break
        if not executor:
            click.secho(f"Invalid executor id [{executor_id}]", fg="red")
        required_params = set(executor['parameters_metadata'].keys())
        given_params = set(executor_params.keys()) # TODO check issue with not required params
        if required_params.symmetric_difference(given_params) != set():
            click.secho(f"Executor Params difference [Required: {required_params} / Given: {given_params}]")
            return
        response = api_client.run_executor(workspace_name, agent_id, executor['name'], executor_params)
        click.secho(f"Run executor: {agent['name']}/{executor['name']} [{response}]", fg="green")

    if action == "list":
        _list_agents(workspace_name)

    elif action == 'get':
        if not agent_id:
            click.secho("Agent ID is required to get an agent", fg="red")
        else:
            _get_agent(workspace_name, agent_id)

    elif action == 'run':
        if not agent_id or not executor_id or not executor_params:
            click.secho("Agent ID, executor ID and executor params are required to run an executor", fg="red")
        else:
            _run_executor(workspace_name, agent_id, executor_id, executor_params)




