import json
import random
import string

import yaml
from click.testing import CliRunner
from faraday_cli.cli.faraday import cli


def test_workspaces(ok_configuration_file):
    runner = CliRunner()
    workspace_name = "".join(
        random.choice(string.ascii_lowercase) for i in range(10)
    )
    cli_execution = runner.invoke(
        cli, ["workspace", "-a", "create", "-n", workspace_name]
    )
    assert cli_execution.exit_code == 0
    assert f"Created workspace: {workspace_name}" in cli_execution.output
    cli_execution = runner.invoke(cli, ["workspace", "--json-output"])
    json_output = json.loads(cli_execution.output)
    number_of_ws = len(json_output)
    assert cli_execution.exit_code == 0
    cli_execution = runner.invoke(
        cli, ["workspace", "-a", "delete", "-n", workspace_name]
    )
    assert cli_execution.exit_code == 0
    assert f"Deleted workspace: {workspace_name}" in cli_execution.output
    cli_execution = runner.invoke(cli, ["workspace", "--json-output"])
    json_output = json.loads(cli_execution.output)
    assert cli_execution.exit_code == 0
    assert len(json_output) == (number_of_ws - 1)


def test_select_workspace(ok_configuration_file):
    runner = CliRunner()
    workspace_name = "".join(
        random.choice(string.ascii_lowercase) for i in range(10)
    )
    cli_execution = runner.invoke(
        cli, ["workspace", "-a", "create", "-n", workspace_name]
    )
    assert cli_execution.exit_code == 0
    assert f"Created workspace: {workspace_name}" in cli_execution.output
    cli_execution = runner.invoke(
        cli, ["workspace", "-a", "select", "-n", workspace_name]
    )
    assert cli_execution.exit_code == 0
    assert f"Selected workspace: {workspace_name}" in cli_execution.output
    with open(ok_configuration_file.name) as f:
        config_data = yaml.load(f, Loader=yaml.FullLoader)
    assert cli_execution.exit_code == 0
    assert config_data["workbench"]["workspace"] == workspace_name
    cli_execution = runner.invoke(
        cli, ["workspace", "-a", "delete", "-n", workspace_name]
    )
    assert cli_execution.exit_code == 0
    assert f"Deleted workspace: {workspace_name}" in cli_execution.output
