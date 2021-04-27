import json
import sys
import argparse
from collections import OrderedDict

import cmd2
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.extras.halo.halo import Halo
from faraday_cli.config import active_config


HOST_CREATE_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "ip": {"type": "string"},
            "description": {"type": "string"},
            "hostnames": {"type": "array"},
        },
        "required": ["ip", "description"],
    },
}


class ServiceCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    # List Service
    list_service_parser = cmd2.Cmd2ArgumentParser()
    list_service_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace"
    )
    list_service_parser.add_argument(
        "-j", "--json-output", action="store_true", help="JSON output"
    )
    list_service_parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty Tables"
    )

    @cmd2.as_subcommand_to(
        "service", "list", list_service_parser, help="list services"
    )
    def list_services(self, args: argparse.Namespace):
        """List services"""

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_data(workspace_name):
            services = self._cmd.api_client.get_services(workspace_name)
            for i in services["services"]:
                i["value"]["host"] = get_service_host(i["value"]["host_id"])
            return services

        host_cache = {}

        def get_service_host(host_id):
            if host_id not in host_cache:
                host_cache[host_id] = self._cmd.api_client.get_host(
                    workspace_name, host_id
                )
            return host_cache[host_id]

        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            services = get_data(workspace_name)
        except NotFoundError:
            self._cmd.perror("Workspace not found")
        else:
            if not services["services"]:
                self._cmd.perror(f"No services in workspace: {workspace_name}")
            else:
                if args.json_output:
                    self._cmd.poutput(
                        json.dumps(services["services"], indent=4)
                    )
                else:

                    data = [
                        OrderedDict(
                            {
                                "ID": x["id"],
                                "NAME": x["value"]["name"],
                                "SUMMARY": x["value"]["summary"],
                                "IP": x["value"]["host"]["ip"],
                                "PORT": x["value"]["port"],
                                "PROTOCOL": x["value"]["protocol"],
                                "HOST": x["value"]["host_id"],
                                "VULNERABILITIES": x["value"]["vulns"],
                            }
                        )
                        for x in sorted(
                            services["services"],
                            key=lambda x: x["value"]["host_id"],
                        )
                    ]
                    self._cmd.poutput(
                        tabulate(
                            data,
                            headers="keys",
                            tablefmt="psql" if args.pretty else "simple",
                        )
                    )
