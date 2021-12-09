import os
import re
from urllib.parse import urljoin
import json
import click
from faraday_cli.api_client.exceptions import (
    DuplicatedError,
    InvalidCredentials,
    Invalid2FA,
    MissingConfig,
    ExpiredLicense,
    NotFound,
    RequestError,
)
from simple_rest_client.api import API


from faraday_cli.api_client import resources, exceptions
from simple_rest_client.exceptions import (
    AuthError,
    NotFoundError,
    ClientError,
    ClientConnectionError,
)

DEFAULT_TIMEOUT = int(os.environ.get("FARADAY_CLI_TIMEOUT", 10000))


class FaradayApi:
    def __init__(self, url=None, ignore_ssl=False, token=None):
        if url:
            self.api_url = urljoin(url, "_api")
        else:
            self.api_url = None
        self.token = token
        if self.token:
            headers = {"Authorization": f"Token {self.token}"}
        else:
            headers = {}
        ssl_verify = not ignore_ssl
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

    def handle_errors(func):
        def hanlde(self, *args, **kwargs):
            if not self.token:
                raise MissingConfig("Missing Config, run 'faraday-cli auth'")
            try:
                result = func(self, *args, **kwargs)
            except InvalidCredentials:
                raise
            except AuthError:
                raise InvalidCredentials(
                    "Invalid credentials, run 'faraday-cli auth'"
                )
            except ClientConnectionError as e:
                raise Exception(
                    f"Connection error: {e} (check you faraday server)"
                )
            except DuplicatedError as e:
                raise Exception(f"{e}")
            except NotFoundError:
                raise NotFound("Element not found")
            except ClientError as e:
                if e.response.status_code == 402:
                    raise ExpiredLicense("Your Faraday license is expired")
                else:
                    if (
                        e.response.headers["content-type"]
                        == "application/json"
                    ):
                        raise RequestError(
                            e.response.body.get("message", e.response.body)
                        )
                    else:
                        raise RequestError(e)
            except Exception as e:
                raise Exception(f"Unknown error: {type(e)} - {e}")
            else:
                return result

        return hanlde

    def _build_resources(self):
        self.faraday_api.add_resource(
            resource_name="login", resource_class=resources.LoginResource
        )
        self.faraday_api.add_resource(
            resource_name="config", resource_class=resources.ConfigResource
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
        self.faraday_api.add_resource(
            resource_name="vuln", resource_class=resources.VulnResource
        )
        self.faraday_api.add_resource(
            resource_name="vuln_evidence",
            resource_class=resources.VulnEvidenceResource,
            json_encode_body=False,
        )
        self.faraday_api.add_resource(
            resource_name="executive_report",
            resource_class=resources.ExecutiveReportResource,
        )

    def login(self, user, password):
        body = {"email": user, "password": password}
        try:
            response = self.faraday_api.login.auth(body=body)
            if response.status_code == 202:
                return None
        except NotFoundError:
            raise
        except AuthError:
            return False
        except ClientConnectionError:
            raise
        else:
            return True

    def get_token(self, second_factor=None):
        if not self.token:
            try:
                # self.faraday_api.login.auth(body=login_body)
                if second_factor:
                    second_factor_body = {"secret": second_factor}
                    try:
                        self.faraday_api.login.second_factor(
                            body=second_factor_body
                        )
                    except AuthError:
                        raise Invalid2FA("Invalid 2FA")
                token_response = self.faraday_api.login.get_token()
            except NotFoundError:
                # raise Exception(
                #    f"Invalid url: {self.faraday_api.api_root_url}"
                # )
                raise
            except AuthError:
                raise InvalidCredentials()
            except ClientConnectionError:
                raise
            else:
                self.token = token_response.body
        return self.token

    @handle_errors
    def is_token_valid(self):
        try:
            self.faraday_api.login.validate()
        except ClientConnectionError as e:
            raise click.ClickException(
                click.style(f"Connection to error: {e}", fg="red")
            )
        except AuthError:
            return False
        else:
            return True

    @handle_errors
    def get_user(self):
        try:
            response = self.faraday_api.login.whoami()
        except NotFoundError:
            return "faraday"  # Community dont have the whoami endpoint
        else:
            return response.body["loggerUser"]["name"]

    @handle_errors
    def get_version(self):
        version_regex = r"(?P<product>\w)?-?(?P<version>\d+\.\d+)"
        response = self.faraday_api.config.config()
        raw_version = response.body["ver"]
        match = re.match(version_regex, raw_version)
        products = {"p": "pro", "c": "corp"}
        product = products.get(match.group("product"), "community")
        version = match.group("version")
        return {"product": product, "version": version}

    @handle_errors
    def get_workspaces(self, get_inactives=False):
        response = self.faraday_api.workspace.list()
        if get_inactives:
            return response.body
        else:
            return [
                workspace for workspace in response.body if workspace["active"]
            ]

    @handle_errors
    def get_workspace(self, workspace_name: str):
        response = self.faraday_api.workspace.get(workspace_name)
        return response.body

    @handle_errors
    def filter_workspaces(self, query_filter: dict):
        response = self.faraday_api.workspace.filter(
            params={"q": json.dumps(query_filter)}
        )
        return response.body

    @handle_errors
    def get_workspace_activities(self, workspace_name: str):
        response = self.faraday_api.workspace.activities(workspace_name)
        return response.body

    @handle_errors
    def get_hosts(self, workspace_name: str, port: int = None):
        if port:
            response = self.faraday_api.host.list(
                workspace_name, params={"port": port}
            )
        else:
            response = self.faraday_api.host.list(workspace_name)
        return response.body

    @handle_errors
    def get_services(self, workspace_name: str):
        response = self.faraday_api.service.list(workspace_name)
        return response.body

    @handle_errors
    def get_vuln(self, workspace_name: str, vulnerability_id: int):
        response = self.faraday_api.vuln.get(workspace_name, vulnerability_id)
        return response.body

    @handle_errors
    def upload_evidence_to_vuln(
        self, workspace_name: str, vulnerability_id: int, image_path: str
    ):
        files = {"file": open(image_path, "rb")}
        original_headers = self.faraday_api.headers.copy()
        self.faraday_api.headers.pop(
            "Content-Type"
        )  # This hack is for this issue
        # https://github.com/allisson/python-simple-rest-client/issues/41
        response = self.faraday_api.vuln_evidence.create(
            workspace_name, vulnerability_id, files=files
        )
        self.faraday_api.headers = original_headers
        return response.body

    @handle_errors
    def get_vulns(self, workspace_name: str, query_filter: dict = None):
        if query_filter.get("filters"):
            response = self.faraday_api.vuln.filter(
                workspace_name, params={"q": json.dumps(query_filter)}
            )
        else:
            response = self.faraday_api.vuln.list(
                workspace_name, params={"sort": "severity", "sort_dir": "asc"}
            )
        return response.body

    @handle_errors
    def get_workspace_credentials(self, workspace_name: str):
        response = self.faraday_api.credential.list(workspace_name)
        return response.body

    @handle_errors
    def get_workspace_agents(self, workspace_name: str):
        response = self.faraday_api.agent.list(workspace_name)
        return response.body

    @handle_errors
    def get_agent(self, workspace_name: str, agent_id: int):
        response = self.faraday_api.agent.get(workspace_name, agent_id)
        return response.body

    @handle_errors
    def run_executor(self, workspace_name: str, agent_id, executor_name, args):
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
    def get_host(self, workspace_name: str, host_id):
        response = self.faraday_api.host.get(workspace_name, host_id)
        return response.body

    @handle_errors
    def delete_host(self, workspace_name: str, host_id):
        response = self.faraday_api.host.delete(workspace_name, host_id)
        return response.body

    @handle_errors
    def create_host(self, workspace_name: str, host_params):
        try:
            response = self.faraday_api.host.create(
                workspace_name, body=host_params
            )
        except ClientError as e:
            if e.response.status_code == 409:
                raise exceptions.DuplicatedError("Host already exist")
            else:
                raise
        else:
            return response.body

    @handle_errors
    def get_host_services(self, workspace_name: str, host_id):
        response = self.faraday_api.host.get_services(workspace_name, host_id)
        return response.body

    @handle_errors
    def get_host_vulns(self, workspace_name: str, host_ip):
        response = self.faraday_api.host.get_vulns(
            workspace_name, params={"target": host_ip}
        )
        return response.body

    @handle_errors
    def bulk_create(self, workspace_name, data):
        response = self.faraday_api.bulk_create.create(
            workspace_name, body=data
        )
        return response.body

    @handle_errors
    def create_workspace(
        self, workspace_name: str, description="", users=None
    ):
        default_users = ["faraday"]
        if users:
            if isinstance(users, str):
                default_users.append(users)
            elif isinstance(users, list):
                default_users.extend(users)
        data = {
            "description": description,
            "id": 0,
            "name": workspace_name,
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
                raise
        else:
            return response.body

    @handle_errors
    def disable_workspace(self, workspace_name: str):
        try:
            response = self.faraday_api.workspace.update(
                workspace_name, body={"active": False}
            )
        except ClientError:
            raise
        else:
            return response.body

    @handle_errors
    def enable_workspace(self, workspace_name: str):
        try:
            response = self.faraday_api.workspace.update(
                workspace_name, body={"active": True}
            )
        except ClientError:
            raise
        else:
            return response.body

    @handle_errors
    def delete_workspace(self, workspace_name: str):
        response = self.faraday_api.workspace.delete(workspace_name)
        return response

    @handle_errors
    def is_workspace_available(self, workspace_name):
        workspaces = self.get_workspaces()
        available_workspaces = [
            ws for ws in map(lambda x: x["name"], workspaces)
        ]
        return workspace_name in available_workspaces

    @handle_errors
    def get_executive_report_templates(self, workspace_name: str):
        response = self.faraday_api.executive_report.list_templates(
            workspace_name
        )
        return response.body

    @handle_errors
    def generate_executive_report(
        self, workspace_name: str, report_data: dict
    ):
        response = self.faraday_api.executive_report.generate(
            workspace_name, body=report_data
        )
        return response.body["id"]

    @handle_errors
    def get_executive_report_status(self, workspace_name: str, report_id: int):
        response = self.faraday_api.executive_report.status(
            workspace_name, report_id
        )
        return response.body["status"]

    @handle_errors
    def download_executive_report(self, workspace_name: str, report_id: int):
        response = self.faraday_api.executive_report.download(
            workspace_name, report_id
        )
        return response
