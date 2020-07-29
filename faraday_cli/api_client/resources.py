from simple_rest_client.resource import Resource


class LoginResource(Resource):
    actions = {"auth": {"method": "POST", "url": "login"},
               "get_token": {"method": "GET", "url": "v2/token/"}}


class WorkspaceResource(Resource):
    actions = {"list": {"method": "GET", "url": "v2/ws/"},
               "get": {"method": "GET", "url": "v2/ws/{}/"},
               "create": {"method": "POST", "url": "v2/ws/"},
               "delete": {"method": "DELETE", "url": "v2/ws/{}/"},
               }


class BulkCreateResource(Resource):
    actions = {"create": {"method": "POST", "url": "v2/ws/{}/bulk_create/"}}


class HostResource(Resource):
    actions = {"list": {"method": "GET", "url": "v2/ws/{}/hosts/"}}