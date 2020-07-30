from urllib.parse import urljoin
import click
from simple_rest_client.api import API


from faraday_cli.api_client import resources
from simple_rest_client.exceptions import AuthError, NotFoundError

SESSION_KEY = "faraday_session_2"

class FaradayApi:

    def __init__(self, url, ssl_verify=True, session=None):
        self.api_url = urljoin(url, "_api")
        self.session = session
        if self.session:
            headers = {"Cookie": f"{SESSION_KEY}={self.session}"}
            #headers = {"Authorization": f"Token {self.session}"}
        else:
            headers = {}
        self.faraday_api = API(api_root_url=self.api_url, params={}, headers=headers, timeout=10, append_slash=False,
                               json_encode_body=True, ssl_verify=ssl_verify)
        self._build_resources()

    def _build_resources(self):
        self.faraday_api.add_resource(resource_name="login", resource_class=resources.LoginResource)
        self.faraday_api.add_resource(resource_name="workspace", resource_class=resources.WorkspaceResource)
        self.faraday_api.add_resource(resource_name="bulk_create", resource_class=resources.BulkCreateResource)
        self.faraday_api.add_resource(resource_name="host", resource_class=resources.HostResource)
        self.faraday_api.add_resource(resource_name="service", resource_class=resources.ServiceResource)

    def get_session(self, user, password):
        if not self.session:
            body = {'email': user, 'password': password}
            try:
                response = self.faraday_api.login.auth(body=body)
                #token_response = self.faraday_api.login.get_token()
            except NotFoundError:
                raise Exception(f"Invalid url: {self.faraday_api.api_root_url}")
            except AuthError:
                raise Exception("Invalid credentials")
            else:
                self.session = response.client_response.cookies.get(SESSION_KEY)
                #self.token = token_response.body
        return self.session

    def get_workspaces(self):
        try:
            response = self.faraday_api.workspace.list()
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def get_workspace(self, workspace_name):
        try:
            response = self.faraday_api.workspace.get(workspace_name)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def get_hosts(self, workspace_name):
        try:
            response = self.faraday_api.host.list(workspace_name)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def get_host(self, workspace_name, host_id):
        try:
            response = self.faraday_api.host.get(workspace_name, host_id)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def delete_host(self, workspace_name, host_id):
        try:
            response = self.faraday_api.host.delete(workspace_name, host_id)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def get_host_services(self, workspace_name, host_id):
        try:
            response = self.faraday_api.host.get_services(workspace_name, host_id)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def bulk_create(self, ws, data):
        try:
            response = self.faraday_api.bulk_create.create(ws, body=data)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def create_workspace(self, name, description="", users=None):
        try:
            default_users = ["faraday"]
            if users:
                if isinstance(users, str):
                    default_users.append(users)
                elif isinstance(users, list):
                    default_users.extend(users)
            data = {"description": description,
                    "id": 0,
                    "name": name,
                    "public": False,
                    "readonly": False,
                    "customer": "",
                    "users": default_users
                }
            response = self.faraday_api.workspace.create(body=data)
            return response.body
        except AuthError:
            raise Exception("Invalid credentials")

    def delete_workspace(self, name):
        try:
            response = self.faraday_api.workspace.delete(name)
            return response
        except AuthError:
            raise Exception("Invalid credentials")

    def is_workspace_valid(self, name):
        workspaces = self.get_workspaces()
        available_workspaces = [ws for ws in map(lambda x: x['name'], workspaces)]
        return name in available_workspaces
