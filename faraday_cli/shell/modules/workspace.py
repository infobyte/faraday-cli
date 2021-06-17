import json
import argparse
from collections import OrderedDict

import cmd2
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate

from faraday_cli.config import active_config
from faraday_cli.shell.utils import (
    get_active_workspaces_filter,
    SEVERITY_COLORS,
)


class WorkspaceCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    select_ws_parser = cmd2.Cmd2ArgumentParser()
    select_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )

    @cmd2.as_subcommand_to(
        "workspace", "select", select_ws_parser, help="select active workspace"
    )
    def select_ws(self, args: argparse.Namespace):
        """Select active Workspace"""
        if self._cmd.api_client.is_workspace_valid(args.workspace_name):
            active_config.workspace = args.workspace_name
            active_config.save()
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['check']} "
                    f"Selected workspace: {args.workspace_name}",
                    fg="green",
                )
            )
            self._cmd.update_prompt()
        else:
            self._cmd.perror(
                f"{self._cmd.emojis['cross']} "
                f"Invalid workspace: {args.workspace_name}"
            )

    # Get Workspace
    get_ws_parser = argparse.ArgumentParser()
    get_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )
    get_ws_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    get_ws_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to(
        "workspace", "get", get_ws_parser, help="get a workspace"
    )
    def get_ws(self, args: argparse.Namespace):
        """Get Workspace"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            workspace = self._cmd.api_client.get_workspace(workspace_name)
        except NotFoundError:
            self._cmd.perror(f"Workspace {workspace_name} not found")
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(workspace, indent=4))
                return
            else:
                data = [
                    {
                        "NAME": workspace["name"],
                        "ACTIVE": workspace["active"],
                        "PUBLIC": workspace["public"],
                        "READONLY": workspace["readonly"],
                        "HOSTS": "-"
                        if workspace["stats"]["hosts"] == 0
                        else workspace["stats"]["hosts"],
                        "SERVICES": "-"
                        if workspace["stats"]["services"] == 0
                        else workspace["stats"]["services"],
                        "VULNS": "-"
                        if workspace["stats"]["total_vulns"] == 0
                        else workspace["stats"]["total_vulns"],
                    }
                ]
                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                        if args.pretty
                        else "simple",
                    )
                )

    # Delete Workspace
    delete_ws_parser = argparse.ArgumentParser()
    delete_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )

    @cmd2.as_subcommand_to(
        "workspace", "delete", delete_ws_parser, help="delete a workspace"
    )
    def delete_ws(self, args: argparse.Namespace):
        """Delete Workspace"""
        workspaces = self._cmd.api_client.get_workspaces()
        workspace_choices = [ws for ws in map(lambda x: x["name"], workspaces)]
        workspace_name = args.workspace_name
        if workspace_name not in workspace_choices:
            self._cmd.perror(f"Invalid workspace: {workspace_name}")
            return
        self._cmd.api_client.delete_workspace(workspace_name)
        self._cmd.poutput(
            cmd2.style(f"Deleted workspace: {args.workspace_name}", fg="green")
        )
        if active_config.workspace == workspace_name:
            active_config.workspace = None
            active_config.save()
        self._cmd.update_prompt()

    # Create Workspace

    create_ws_parser = argparse.ArgumentParser()
    create_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )
    create_ws_parser.add_argument(
        "-d",
        "--dont-select",
        action="store_true",
        help="Dont select after create",
    )

    @cmd2.as_subcommand_to(
        "workspace", "create", create_ws_parser, help="create a workspace"
    )
    def create_ws(self, args: argparse.Namespace):
        """Create Workspace"""
        workspace_name = args.workspace_name
        try:
            self._cmd.api_client.create_workspace(workspace_name)
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['check']} "
                    f"Created workspace: {args.workspace_name}",
                    fg="green",
                )
            )
            if not args.dont_select:
                active_config.workspace = workspace_name
                active_config.save()
                self._cmd.update_prompt()

    # List Workspace
    list_ws_parser = cmd2.Cmd2ArgumentParser()
    list_ws_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    list_ws_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )
    list_ws_parser.add_argument(
        "--show-inactive", action="store_true", help="Show inactive workspaces"
    )

    @cmd2.as_subcommand_to(
        "workspace", "list", list_ws_parser, help="list workspaces"
    )
    def list_workspace(self, args: argparse.Namespace):
        """List Workspaces"""
        workspaces = self._cmd.api_client.get_workspaces(
            get_inactives=args.show_inactive
        )
        if args.json_output:
            self._cmd.poutput(json.dumps(workspaces, indent=4))
            return
        else:
            if not workspaces:
                self._cmd.poutput("No workspaces available")
                return
            else:
                data = [
                    OrderedDict(
                        {
                            "NAME": x["name"],
                            "HOSTS": x["stats"]["hosts"],
                            "SERVICES": x["stats"]["services"],
                            "VULNS": "-"
                            if x["stats"]["total_vulns"] == 0
                            else x["stats"]["total_vulns"],
                            "ACTIVE": x["active"],
                            "PUBLIC": x["public"],
                            "READONLY": x["readonly"],
                        }
                    )
                    for x in workspaces
                ]
                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                        if args.pretty
                        else "simple",
                    )
                )

    # Workspace Dashboard
    @cmd2.as_subcommand_to(
        "workspace", "dashboard", list_ws_parser, help="workspaces dashboard"
    )
    def workspaces_dashboard(self, args: argparse.Namespace):
        """Workspaces Dashboard """
        SEVERITY_COUNTER_KEYS = (
            ("critical_vulns", "critical"),
            ("high_vulns", "high"),
            ("medium_vulns", "med"),
            ("low_vulns", "low"),
            ("info_vulns", "info"),
            ("unclassified_vulns", "unclassified"),
        )
        ASSETS_COUNTER_KEYS = (
            ("hosts", "hosts"),
            ("services", "services"),
            ("total_vulns", "vulns"),
        )
        INFO_KEYS = (
            ("create_date", "created", lambda x: x),
            ("update_date", "updated", lambda x: x),
        )
        workspaces_info = self._cmd.api_client.filter_workspaces(
            query_filter=get_active_workspaces_filter()
        )
        if not workspaces_info:
            self._cmd.poutput("No workspaces available")
            return
        else:
            data = []
            data_headers = ["Workspace", "Info", "Severities", "Assets"]
            for workspace_info in workspaces_info:
                workspace_data = OrderedDict(
                    {
                        "name": workspace_info["name"],
                        "info": [],
                        "severities": [],
                        "assets": [],
                    }
                )
                for key, severity in SEVERITY_COUNTER_KEYS:
                    value = workspace_info["stats"][key]
                    severity_text = cmd2.style(
                        severity, fg=SEVERITY_COLORS[severity]
                    )
                    text = f"{severity_text}:" f" {value}"
                    workspace_data["severities"].append(text)
                for key, name, parser in INFO_KEYS:
                    value = workspace_info[key]
                    workspace_data["info"].append(
                        f"{name}\n[{value if not parser else parser(value)}]"
                    )
                for key, name in ASSETS_COUNTER_KEYS:
                    value = workspace_info["stats"][key]
                    workspace_data["assets"].append(f"{name}: {value}")
                data.append(
                    [
                        "\n".join(item) if type(item) == list else item
                        for item in workspace_data.values()
                    ]
                )
            self._cmd.poutput(tabulate(data, data_headers, "grid"))
