import json
import argparse
import sys
from collections import OrderedDict

import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.extras.halo.halo import Halo
from faraday_cli.config import active_config
from faraday_cli.shell import utils

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


class HostCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    # List Host
    list_host_parser = cmd2.Cmd2ArgumentParser()
    list_host_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace name"
    )
    list_host_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    list_host_parser.add_argument(
        "-ip", "--show-ip", action="store_true", help="Show ip only"
    )
    list_host_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )
    list_host_parser.add_argument("--port", type=int, help="Listen in port")

    @cmd2.as_subcommand_to("host", "list", list_host_parser, help="list hosts")
    def list_hosts(self, args: argparse.Namespace):
        """List hosts"""

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_data(workspace_name, port_number):
            hosts = self._cmd.api_client.get_hosts(workspace_name, port_number)
            return hosts

        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            hosts = get_data(workspace_name, args.port)
        except NotFoundError:
            self._cmd.perror("Workspace not found")
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(hosts["rows"], indent=4))
            elif args.show_ip:
                for host in hosts["rows"]:
                    self._cmd.poutput(host["value"]["ip"])
            else:
                if not hosts["rows"]:
                    self._cmd.perror(
                        f"No hosts in workspace: {workspace_name}"
                    )
                else:
                    data = [
                        OrderedDict(
                            {
                                "ID": x["value"]["id"],
                                "IP": x["value"]["ip"],
                                "OS": x["value"]["os"],
                                "HOSTNAMES": "\n".join(
                                    x["value"]["hostnames"]
                                ),
                                "SERVICES": "-"
                                if len(x["value"]["service_summaries"]) == 0
                                else len(x["value"]["service_summaries"]),
                                "VULNS": "-"
                                if x["value"]["vulns"] == 0
                                else x["value"]["vulns"],
                            }
                        )
                        for x in hosts["rows"]
                    ]
                    self._cmd.print_output(
                        tabulate(
                            data,
                            headers="keys",
                            tablefmt="psql" if args.pretty else "simple",
                        )
                    )

    get_host_parser = argparse.ArgumentParser()
    get_host_parser.add_argument("host_id", type=int, help="ID of the host")
    get_host_parser.add_argument(
        "-w",
        "--workspace-name",
        type=str,
        help="Workspace name",
        required=False,
    )
    get_host_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    get_host_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to("host", "get", get_host_parser, help="get a host")
    def get_host(self, args: argparse.Namespace):
        """Get host information"""

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_host_data(workspace_name, host_id):
            return self._cmd.api_client.get_host(workspace_name, host_id)

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_host_services(workspace_name, host_id):
            return self._cmd.api_client.get_host_services(
                workspace_name, host_id
            )

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_host_vulns(workspace_name, ip):
            return self._cmd.api_client.get_host_vulns(workspace_name, ip)

        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            host = get_host_data(workspace_name, args.host_id)
        except NotFoundError:
            self._cmd.perror(
                f"Host ID: {args.host_id} "
                f"in Workspace {workspace_name} not found"
            )
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(host, indent=4))
            else:
                host_data = [
                    OrderedDict(
                        {
                            "ID": x["id"],
                            "IP": x["ip"],
                            "OS": x["os"],
                            "HOSTNAMES": "\n".join(x["hostnames"]),
                            "OWNER": x["owner"],
                            "OWNED": x["owned"],
                            "VULNS": "-" if x["vulns"] == 0 else x["vulns"],
                        }
                    )
                    for x in [host]
                ]
                self._cmd.print_output("Host:")
                self._cmd.print_output(
                    tabulate(
                        host_data,
                        headers="keys",
                        tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                        if args.pretty
                        else "simple",
                    )
                )
                if host["services"] > 0:
                    services = get_host_services(workspace_name, args.host_id)
                    services_data = [
                        OrderedDict(
                            {
                                "ID": x["id"],
                                "NAME": x["name"],
                                "DESCRIPTION": x["description"],
                                "PROTOCOL": x["protocol"],
                                "PORT": x["port"],
                                "VERSION": x["version"],
                                "STATUS": x["status"],
                                "VULNS": "-"
                                if x["vulns"] == 0
                                else x["vulns"],
                            }
                        )
                        for x in services
                    ]
                    self._cmd.print_output("\nServices:")
                    self._cmd.print_output(
                        tabulate(
                            services_data,
                            headers="keys",
                            tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                            if args.pretty
                            else "simple",
                        )
                    )
                if host["vulns"] > 0:
                    vulns = get_host_vulns(workspace_name, host["ip"])
                    vulns_data = [
                        OrderedDict(
                            {
                                "ID": x["id"],
                                "NAME": x["value"]["name"],
                                "SEVERITY": cmd2.style(
                                    x["value"]["severity"].upper(),
                                    fg=utils.get_severity_color(
                                        x["value"]["severity"]
                                    ),
                                ),
                                "STATUS": x["value"]["status"],
                                "CONFIRMED": x["value"]["confirmed"],
                                "TOOL": x["value"]["metadata"]["creator"],
                            }
                        )
                        for x in vulns["vulnerabilities"]
                    ]
                    self._cmd.print_output("\nVulnerabilities:")
                    self._cmd.print_output(
                        tabulate(
                            vulns_data,
                            headers="keys",
                            tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                            if args.pretty
                            else "simple",
                        )
                    )

    # Delete Host
    delete_host_parser = argparse.ArgumentParser()
    delete_host_parser.add_argument("host_id", type=int, help="ID of the host")
    delete_host_parser.add_argument(
        "-w",
        "--workspace-name",
        type=str,
        help="Workspace name",
        required=False,
    )

    @cmd2.as_subcommand_to(
        "host", "delete", delete_host_parser, help="delete a host"
    )
    def delete_host(self, args):
        """Delete Host"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            self._cmd.api_client.delete_host(workspace_name, args.host_id)
        except NotFoundError:
            self._cmd.perror("Host not found")
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            self._cmd.poutput(cmd2.style("Host deleted", fg=COLORS.GREEN))

    # Create hosts
    create_host_parser = argparse.ArgumentParser()
    create_host_parser.add_argument(
        "-d",
        "--host-data",
        type=str,
        help=f"Host data in json format: {HOST_CREATE_JSON_SCHEMA}",
    )
    create_host_parser.add_argument(
        "--stdin", action="store_true", help="Read host-data from stdin"
    )
    create_host_parser.add_argument(
        "-w",
        "--workspace-name",
        type=str,
        help="Workspace name",
        required=False,
    )

    @cmd2.as_subcommand_to(
        "host", "create", create_host_parser, help="create hosts"
    )
    def create_hosts(self, args: argparse.Namespace):
        """Create Hosts"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        if args.stdin:
            host_data = sys.stdin.read()
        else:
            if not args.host_data:
                self._cmd.perror("Missing host data")
                return
            else:
                host_data = args.host_data
        try:
            json_data = utils.json_schema_validator(HOST_CREATE_JSON_SCHEMA)(
                host_data
            )
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            for _host_data in json_data:
                ip, hostname = utils.get_ip_and_hostname(_host_data["ip"])
                _host_data["ip"] = ip
                if hostname:
                    if "hostnames" in _host_data:
                        _host_data["hostnames"].append(hostname)
                    else:
                        _host_data["hostnames"] = [hostname]
                try:
                    host = self._cmd.api_client.create_host(
                        workspace_name, _host_data
                    )
                except Exception as e:
                    self._cmd.perror(f"{e}")
                else:
                    self._cmd.poutput(
                        f"Created host\n{json.dumps(host, indent=4)}"
                    )
