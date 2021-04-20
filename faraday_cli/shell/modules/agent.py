import json
import argparse
import sys
from collections import OrderedDict

import cmd2
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
        "-w", "--workspace-name", type=str, help="Workspace name"
    )
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
        "list", "agents", list_agent_parser, help="list agents"
    )
    def list_agents(self, args: argparse.Namespace):
        """List agents"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            agents = self._cmd.api_client.get_workspace_agents(workspace_name)
        except NotFoundError:
            self._cmd.perror("Workspace not found")
        else:
            if not agents:
                self._cmd.perror(f"No agents in workspace: {workspace_name}")
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
        "-w", "--workspace-name", type=str, help="Workspace name "
    )
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
        "get", "agent", get_agent_parser, help="get an agent"
    )
    def get_agent(self, args: argparse.Namespace):
        """Get agent"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            agent = self._cmd.api_client.get_agent(
                workspace_name, args.agent_id
            )
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
                            "PARAMETERS [REQUIRED]": "".join(
                                [
                                    f"{parameter} [{required}]\n"
                                    for parameter, required in x[
                                        "parameters_metadata"
                                    ].items()
                                ]
                            ),
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
        "-w", "--workspace-name", type=str, help="Workspace name"
    )

    @cmd2.as_subcommand_to(
        "run", "executor", run_executor_parser, help="run an executor"
    )
    def run_executor(self, args):
        """Run executor"""
        if args.stdin:
            executor_params = sys.stdin.read()
        else:
            if not args.executor_params:
                self._cmd.perror("Missing executor params")
                return
            else:
                executor_params = args.executor_params
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
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
                agent = self._cmd.api_client.get_agent(
                    workspace_name, args.agent_id
                )
            except NotFoundError:
                self._cmd.perror("Agent not found")
            else:
                executor = None
                for executor in agent["executors"]:
                    if executor["name"] == args.executor_name:
                        break
                if not executor:
                    self._cmd.perror(
                        f"Invalid executor name [{args.executor_name}]"
                    )
                    return
                executor_parameters_schema = {
                    "type": "object",
                    "properties": {
                        x: {"type": "string"}
                        for x in executor["parameters_metadata"].keys()
                    },
                    "required": [
                        i[0]
                        for i in filter(
                            lambda x: x[1] is True,
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
                    try:
                        response = self._cmd.api_client.run_executor(
                            workspace_name,
                            args.agent_id,
                            executor["name"],
                            json.loads(executor_params),
                        )
                    except Exception as e:
                        print(e)
                    else:
                        self._cmd.poutput(
                            cmd2.style(
                                f"Run executor: {agent['name']}/{executor['name']} [{response}]",  # noqa: E501
                                fg="green",
                            )
                        )
