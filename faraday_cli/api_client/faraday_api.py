import os
from urllib.parse import urljoin

import click
from simple_rest_client.api import API


from faraday_cli.api_client import resources, exceptions
from simple_rest_client.exceptions import AuthError, NotFoundError, ClientError, ClientConnectionError

SESSION_KEY = "faraday_session_2"
DEFAULT_TIMEOUT = int(os.environ.get("FARADAY_CLI_TIMEOUT", 1000))

def handle_errors(func):

    def hanlde(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except AuthError:
            raise click.ClickException(
                click.style(
                    "Invalid credentials, run 'faraday-cli auth'", fg="red"
                )
            )
        except ClientConnectionError as e:
            raise click.ClickException(
                click.style(
                    f"Connection to error: {e}", fg="red"
                )
            )
        except Exception as e:
            raise click.ClickException(
                click.style(
                    f"Unknown error: {e}", fg="red"
                )
            )
        else:
            return result
    return hanlde

class FaradayApi:
    def __init__(self, url, ssl_verify=True, token=None):
        self.api_url = urljoin(url, "_api")
        self.token = token
        if self.token:
            headers = {"Authorization": f"Token {self.token}"}
        else:
            headers = {}
        self.faraday_api = API(
            api_root_url=self.api_url,
            params={},
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            append_slash=False,
            json_encode_body=True,
            ssl_verify=ssl_verify,
        )
        self._build_resources()

    def _build_resources(self):
        self.faraday_api.add_resource(
            resource_name="login", resource_class=resources.LoginResource
        )
        self.faraday_api.add_resource(
            resource_name="workspace",
            resource_class=resources.WorkspaceResource,
        )
        self.faraday_api.add_resource(
            resource_name="bulk_create",
            resource_class=resources.BulkCreateResource,
        )
        self.faraday_api.add_resource(
            resource_name="host", resource_class=resources.HostResource
        )
        self.faraday_api.add_resource(
            resource_name="service", resource_class=resources.ServiceResource
        )
        self.faraday_api.add_resource(
            resource_name="credential",
            resource_class=resources.CredentialResource,
        )
        self.faraday_api.add_resource(
            resource_name="agent", resource_class=resources.AgentResource
        )

    def get_token(self, user, password):
        if not self.token:
            body = {"email": user, "password": password}
            try:
                self.faraday_api.login.auth(body=body)
                token_response = self.faraday_api.login.get_token()
            except NotFoundError:
                raise Exception(
                    f"Invalid url: {self.faraday_api.api_root_url}"
                )
            except AuthError:
                raise Exception("Invalid credentials")
            else:
                self.token = token_response.body
        return self.token

    @handle_errors
    def get_workspaces(self):
        response = self.faraday_api.workspace.list()
        return response.body

    @handle_errors
    def get_workspace(self, workspace_name):
        response = self.faraday_api.workspace.get(workspace_name)
        return response.body

    @handle_errors
    def get_hosts(self, workspace_name):
        response = self.faraday_api.host.list(workspace_name)
        return response.body

    @handle_errors
    def get_workspace_credentials(self, workspace_name):
        response = self.faraday_api.credential.list(workspace_name)
        return response.body

    @handle_errors
    def get_workspace_agents(self, workspace_name):
        response = self.faraday_api.agent.list(workspace_name)
        return response.body

    @handle_errors
    def get_agent(self, workspace_name, agent_id):
        response = self.faraday_api.agent.get(workspace_name, agent_id)
        return response.body

    @handle_errors
    def run_executor(self, workspace_name, agent_id, executor_name, args):
        body = {
            "executorData": {
                "agent_id": agent_id,
                "args": args,
                "executor": executor_name,
            }
        }
        response = self.faraday_api.agent.run(
            workspace_name, agent_id, body=body
        )
        return response.body

    @handle_errors
    def get_host(self, workspace_name, host_id):
        response = self.faraday_api.host.get(workspace_name, host_id)
        return response.body

    @handle_errors
    def delete_host(self, workspace_name, host_id):
        response = self.faraday_api.host.delete(workspace_name, host_id)
        return response.body

    @handle_errors
    def create_host(self, workspace_name, host_params):
        try:
            response = self.faraday_api.host.create(
                workspace_name, body=host_params
            )
        except ClientError as e:
            if e.response.status_code == 409:
                raise exceptions.DuplicatedError("Host already exist")
        else:
            return response.body

    @handle_errors
    def get_host_services(self, workspace_name, host_id):
        response = self.faraday_api.host.get_services(workspace_name, host_id)
        return response.body

    @handle_errors
    def get_host_vulns(self, workspace_name, host_ip):
        response = self.faraday_api.host.get_vulns(
            workspace_name, params={"target": host_ip}
        )
        return response.body

    @handle_errors
    def bulk_create(self, ws, data):
        response = self.faraday_api.bulk_create.create(ws, body=data)
        return response.body

    @handle_errors
    def create_workspace(self, name, description="", users=None):
        default_users = ["faraday"]
        if users:
            if isinstance(users, str):
                default_users.append(users)
            elif isinstance(users, list):
                default_users.extend(users)
        data = {
            "description": description,
            "id": 0,
            "name": name,
            "public": False,
            "readonly": False,
            "customer": "",
            "users": default_users,
        }
        try:
            response = self.faraday_api.workspace.create(body=data)
        except ClientError as e:
            if e.response.status_code == 409:
                raise exceptions.DuplicatedError("Workspace already exist")
        else:
            return response.body

    @handle_errors
    def delete_workspace(self, name):
        response = self.faraday_api.workspace.delete(name)
        return response

    @handle_errors
    def is_workspace_valid(self, name):
        workspaces = self.get_workspaces()
        available_workspaces = [
            ws for ws in map(lambda x: x["name"], workspaces)
        ]
        return name in available_workspaces
