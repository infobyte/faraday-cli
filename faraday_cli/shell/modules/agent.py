import json
import argparse
import sys
import os
from collections import OrderedDict

import cmd2
from cmd2 import Fg as COLORS
import click
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.config import active_config
from faraday_cli.shell import utils
from faraday_cli.shell.exceptions import InvalidJson, InvalidJsonSchema


@cmd2.with_default_category("Agents")
class AgentCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    # List Agents
    list_agent_parser = argparse.ArgumentParser()
    list_agent_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    list_agent_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to(
        "agent", "list", list_agent_parser, help="list agents"
    )
    def list_agents(self, args: argparse.Namespace):
        """List agents"""
        agents = self._cmd.api_client.list_agents()
        if not agents:
            self._cmd.perror("No agents in server")
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(agents, indent=4))
            else:
                data = [
                    OrderedDict(
                        {
                            "ID": x["id"],
                            "NAME": x["name"],
                            "ACTIVE": x["active"],
                            "STATUS": x["status"],
                            "EXECUTORS": ", ".join(
                                [i["name"] for i in x["executors"]]
                            ),
                        }
                    )
                    for x in agents
                ]

                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt="psql" if args.pretty else "simple",
                    )
                )

    get_agent_parser = argparse.ArgumentParser()
    get_agent_parser.add_argument("agent_id", type=int, help="ID of the Agent")
    get_agent_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    get_agent_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to(
        "agent", "get", get_agent_parser, help="get an agent"
    )
    def get_agent(self, args: argparse.Namespace):
        """Get agent"""
        try:
            agent = self._cmd.api_client.get_agent(args.agent_id)
        except NotFoundError:
            self._cmd.perror("Agent not found")
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(agent, indent=4))
            else:
                data = [
                    OrderedDict(
                        {
                            "ID": x["id"],
                            "NAME": x["name"],
                            "ACTIVE": x["active"],
                            "STATUS": x["status"],
                        }
                    )
                    for x in [agent]
                ]
                executors_data = [
                    OrderedDict(
                        {
                            "ID": x["id"],
                            "NAME": x["name"],
                            "PARAMETERS [TYPE - REQUIRED]": "".join(
                                [
                                    f"{parameter} [Type: "
                                    f"{parameter_data['type']} - Required: "
                                    f"{parameter_data['mandatory']}]\n"
                                    for parameter, parameter_data in x[
                                        "parameters_metadata"
                                    ].items()
                                ]
                            ),
                            "LAST_RUN": x["last_run"],
                        }
                    )
                    for x in agent["executors"]
                ]

                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt="psql" if args.pretty else "simple",
                    )
                )
                self._cmd.poutput("\nExecutors:")
                self._cmd.poutput(
                    tabulate(
                        executors_data,
                        headers="keys",
                        tablefmt="psql" if args.pretty else "simple",
                    )
                )

    run_executor_parser = argparse.ArgumentParser()
    run_executor_parser.add_argument(
        "-a", "--agent-id", type=int, help="ID of the agent", required=True
    )
    run_executor_parser.add_argument(
        "-e", "--executor-name", type=str, help="Executor name", required=True
    )
    run_executor_parser.add_argument(
        "-p",
        "--executor-params",
        type=str,
        help="Executor Params in json",
    )
    run_executor_parser.add_argument(
        "--stdin", action="store_true", help="Read executor-params from stdin"
    )
    run_executor_parser.add_argument(
        "-w",
        "--workspace-name",
        action="append",
        type=str,
        help="Workspace name",
    )
    run_executor_parser.add_argument(
        "--vuln-tag",
        type=str,
        help="Tag to add to vulnerabilities",
        required=False,
        action="append",
        default=[],
    )
    run_executor_parser.add_argument(
        "--host-tag",
        type=str,
        help="Tag to add to hosts",
        required=False,
        action="append",
        default=[],
    )
    run_executor_parser.add_argument(
        "--service-tag",
        type=str,
        help="Tag to add to services",
        required=False,
        action="append",
        default=[],
    )

    @cmd2.as_subcommand_to(
        "agent", "run", run_executor_parser, help="run an executor"
    )
    def run_executor(self, args):
        """Run executor"""
        ask_for_parameters = False
        if isinstance(args.vuln_tag, str):
            args.vuln_tag = [args.vuln_tag]
        if isinstance(args.host_tag, str):
            args.host_tag = [args.host_tag]
        if isinstance(args.service_tag, str):
            args.service_tag = [args.service_tag]
        if args.stdin:
            executor_params = sys.stdin.read()
        else:
            if not args.executor_params:
                ask_for_parameters = True
                # self._cmd.perror("Missing executor params")
                # return
            else:
                executor_params = args.executor_params
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = [active_config.workspace]
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            utils.validate_json(args.executor_params)
        except InvalidJson as e:
            self._cmd.perror(e)
        else:
            try:
                agent = self._cmd.api_client.get_agent(args.agent_id)
            except NotFoundError:
                self._cmd.perror("Agent not found")
            else:
                executor = None
                for executor_data in agent["executors"]:
                    if executor_data["name"] == args.executor_name:
                        executor = executor_data
                        break
                if not executor:
                    self._cmd.perror(
                        f"Invalid executor name [{args.executor_name}]"
                    )
                    return
                if ask_for_parameters:
                    executor_params = {}
                    types_mapping = {
                        "boolean": click.BOOL,
                        "integer": click.INT,
                    }
                    for parameter, parameter_data in executor[
                        "parameters_metadata"
                    ].items():
                        value = os.getenv(
                            f"FARADAY_CLI_EXECUTOR_{executor['name'].upper()}_{parameter}",
                            None,
                        )
                        if value is None:
                            if parameter_data["mandatory"]:
                                value = click.prompt(
                                    f"{parameter} ({parameter_data['type']})",
                                    type=types_mapping.get(
                                        parameter_data["type"], click.STRING
                                    ),
                                    show_default=False,
                                )
                            else:
                                value = click.prompt(
                                    f"{parameter} ({parameter_data['type']})",
                                    default="",
                                    show_default=False,
                                )
                        if type(value) == str and value == "":
                            continue
                        executor_params[parameter] = str(value)
                    executor_params = json.dumps(executor_params)
                executor_parameters_schema = {
                    "type": "object",
                    "properties": {
                        x: {"type": "string"}
                        for x in executor["parameters_metadata"].keys()
                    },
                    "required": [
                        i[0]
                        for i in filter(
                            lambda x: x[1]["mandatory"] is True,
                            executor["parameters_metadata"].items(),
                        )
                    ],
                }
                try:
                    utils.json_schema_validator(executor_parameters_schema)(
                        executor_params
                    )
                except InvalidJsonSchema as e:
                    self._cmd.perror(e)
                else:
                    run_message = (
                        f"Running executor: {agent['name']}/{executor['name']}"
                        f"\nParameters: {executor_params}"
                    )
                    self._cmd.poutput(
                        cmd2.style(
                            run_message,
                            fg=COLORS.GREEN,
                        )
                    )
                    try:
                        response = self._cmd.api_client.run_executor(
                            workspace_name,
                            args.agent_id,
                            executor["name"],
                            json.loads(executor_params),
                            self._cmd.ignore_info_severity,
                            self._cmd.hostname_resolution,
                            args.vuln_tag,
                            args.host_tag,
                            args.service_tag,
                        )
                    except Exception as e:
                        self._cmd.perror(str(e))
                    else:
                        self._cmd.poutput(
                            cmd2.style(
                                f"Generated Command: {response['commands_id']}",  # noqa: E501
                                fg=COLORS.GREEN,
                            )
                        )
