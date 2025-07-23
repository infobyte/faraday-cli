import random
import string
import json
from cmd2 import CommandResult


def test_create_ws(faraday_cli_app):
    workspace_name = "".join(random.choice(string.ascii_lowercase) for i in range(10))
    command = f"workspace create {workspace_name}"
    create_out = faraday_cli_app.app_cmd(command)
    assert isinstance(create_out, CommandResult)
    assert f"Created workspace: {workspace_name}" in create_out.stdout.strip()
    command = f"workspace delete {workspace_name}"
    delete_out = faraday_cli_app.app_cmd(command)
    assert isinstance(delete_out, CommandResult)
    assert f"Deleted workspace: {workspace_name}" in delete_out.stdout.strip()


def test_select_ws(faraday_cli_app):
    workspace_name = "".join(random.choice(string.ascii_lowercase) for i in range(10))
    command = f"workspace create {workspace_name}"
    create_out = faraday_cli_app.app_cmd(command)
    assert isinstance(create_out, CommandResult)
    assert f"Created workspace: {workspace_name}" in create_out.stdout.strip()
    command = f"workspace select {workspace_name}"
    select_out = faraday_cli_app.app_cmd(command)
    assert isinstance(select_out, CommandResult)
    assert f"Selected workspace: {workspace_name}" in select_out.stdout.strip()
    command = f"workspace delete {workspace_name}"
    delete_out = faraday_cli_app.app_cmd(command)
    assert isinstance(delete_out, CommandResult)
    assert f"Deleted workspace: {workspace_name}" in delete_out.stdout.strip()


def test_list_ws(faraday_cli_app):
    workspace_name = "".join(random.choice(string.ascii_lowercase) for i in range(10))
    command = f"workspace create {workspace_name}"
    create_out = faraday_cli_app.app_cmd(command)
    assert isinstance(create_out, CommandResult)
    assert f"Created workspace: {workspace_name}" in create_out.stdout.strip()
    command = "workspace list -j"
    out = faraday_cli_app.app_cmd(command)
    assert isinstance(out, CommandResult)
    workspaces = json.loads(out.stdout.strip())
    workspaces_names = [x["name"] for x in workspaces]
    assert workspace_name in workspaces_names
    command = f"workspace delete {workspace_name}"
    delete_out = faraday_cli_app.app_cmd(command)
    assert isinstance(delete_out, CommandResult)
    assert f"Deleted workspace: {workspace_name}" in delete_out.stdout.strip()
