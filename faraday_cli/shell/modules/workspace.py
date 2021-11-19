import json
import argparse
from collections import OrderedDict
import arrow
import sys

import cmd2
from cmd2 import Fg as COLORS
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate

from faraday_cli.extras.halo.halo import Halo
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
        if self._cmd.api_client.is_workspace_available(args.workspace_name):
            active_config.workspace = args.workspace_name
            active_config.save()
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['check']} "
                    f"Selected workspace: {args.workspace_name}",
                    fg=COLORS.GREEN,
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

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_workspace(workspace_name):
            return self._cmd.api_client.get_workspace(workspace_name)

        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            workspace = get_workspace(workspace_name)
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
                self._cmd.print_output(
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
            cmd2.style(
                f"Deleted workspace: {args.workspace_name}", fg=COLORS.GREEN
            )
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
                    fg=COLORS.GREEN,
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
        "-i",
        "--show-inactive",
        action="store_true",
        help="Show inactive workspaces",
    )

    @cmd2.as_subcommand_to(
        "workspace", "list", list_ws_parser, help="list workspaces"
    )
    def list_workspace(self, args: argparse.Namespace):
        """List Workspaces"""

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_workspaces():
            return self._cmd.api_client.get_workspaces(
                get_inactives=args.show_inactive
            )

        workspaces = get_workspaces()
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
                self._cmd.print_output(
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
        """Workspaces Dashboard"""
        MAX_ACTIVITIES = 10
        EXCLUDE_TOOLS = ("Searcher",)
        SEVERITY_COUNTER_KEYS = (
            ("critical_vulns", "critical"),
            ("high_vulns", "high"),
            ("medium_vulns", "med"),
            ("low_vulns", "low"),
            ("info_vulns", "info"),
        )
        SUMMARY_COUNTER_KEYS = (
            ("hosts", "hosts", None),
            ("services", "services", None),
            ("total_vulns", "vulns", None),
        )

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_workspaces_info():
            workspaces_info = self._cmd.api_client.filter_workspaces(
                query_filter=get_active_workspaces_filter()
            )
            return workspaces_info

        @Halo(
            text="Gathering data",
            text_color="green",
            spinner="dots",
            stream=sys.stderr,
        )
        def get_workspace_activities(workspace_name):
            return self._cmd.api_client.get_workspace_activities(
                workspace_name
            )

        def activities_vulns_parser(activity_data):
            critical_text = cmd2.style(
                activity_data["criticalIssue"], fg=SEVERITY_COLORS["critical"]
            )
            high_text = cmd2.style(
                activity_data["highIssue"], fg=SEVERITY_COLORS["high"]
            )
            med_text = cmd2.style(
                activity_data["mediumIssue"], fg=SEVERITY_COLORS["med"]
            )
            low_text = cmd2.style(
                activity_data["lowIssue"], fg=SEVERITY_COLORS["low"]
            )
            info_text = cmd2.style(
                activity_data["infoIssue"], fg=SEVERITY_COLORS["info"]
            )
            vulns_text = (
                f"and {activity_data['vulnerabilities_count']} vulns ("
                f"{critical_text}/"
                f"{high_text}/"
                f"{med_text}/"
                f"{low_text}/"
                f"{info_text})"
            )
            return vulns_text

        ACTIVITIES_KEYS = (
            ("tool", lambda x: f"{x['tool']} ({x['import_source']})", True),
            ("hosts_count", lambda x: f"found {x} hosts,", False),
            ("services_count", lambda x: f"{x} services", False),
            ("vulnerabilities_count", activities_vulns_parser, True),
            (
                "date",
                lambda x: arrow.get(x).humanize(),
                False,
            ),
            ("creator", lambda x: "" if not x else f"by {x}", False),
        )
        workspaces_info = get_workspaces_info()
        if not workspaces_info:
            self._cmd.poutput("No workspaces available")
            return
        else:
            data = []
            data_headers = [
                "WORKSPACE",
                "SUMMARY",
                "SEVERITIES",
                "ACTIVITY",
            ]
            for workspace_info in workspaces_info:
                activities_info = get_workspace_activities(
                    workspace_info["name"]
                )
                filtered_activities = list(
                    filter(
                        lambda x: x["hosts_count"] > 0
                        and x["tool"] not in EXCLUDE_TOOLS,
                        activities_info["activities"],
                    )
                )
                filtered_activities.sort(reverse=True, key=lambda x: x["date"])
                last_activities = filtered_activities[:MAX_ACTIVITIES]
                workspace_data = OrderedDict(
                    {
                        "name": workspace_info["name"],
                        "summary": [],
                        "severities": [],
                        "activities": [],
                    }
                )
                for key, severity in SEVERITY_COUNTER_KEYS:
                    value = workspace_info["stats"].get(key)
                    severity_text = cmd2.style(
                        severity, fg=SEVERITY_COLORS[severity]
                    )
                    text = f"{severity_text}:" f" {value}"
                    workspace_data["severities"].append(text)
                for key, name, parser in SUMMARY_COUNTER_KEYS:
                    value = workspace_info["stats"].get(key)
                    value_text = value if not parser else parser(value)
                    workspace_data["summary"].append(f"{name}: {value_text}")
                for activity in last_activities:
                    activity_data = []
                    for key, parser, send_full in ACTIVITIES_KEYS:
                        if send_full:
                            value = activity.get(key)
                            value_text = (
                                value if not parser else parser(activity)
                            )
                            activity_data.append(f"{value_text}")
                        else:
                            value = activity.get(key)
                            value_text = value if not parser else parser(value)
                            activity_data.append(f"{value_text}")
                    workspace_data["activities"].append(
                        " ".join(activity_data)
                    )
                data.append(
                    [
                        "\n".join(item) if type(item) == list else item
                        for item in workspace_data.values()
                    ]
                )
            self._cmd.poutput(tabulate(data, data_headers, "grid"))

    # Disable Workspace
    disable_ws_parser = argparse.ArgumentParser()
    disable_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace"
    )

    @cmd2.as_subcommand_to(
        "workspace", "disable", disable_ws_parser, help="disable a workspace"
    )
    def disable_ws(self, args: argparse.Namespace):
        """Disable Workspace"""
        workspace_name = args.workspace_name
        try:
            self._cmd.api_client.disable_workspace(workspace_name)
        except NotFoundError:
            self._cmd.perror(f"Invalid Workspace: {workspace_name}")
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['check']} "
                    f"Disabled workspace: {workspace_name}",
                    fg=COLORS.GREEN,
                )
            )
        if active_config.workspace == workspace_name:
            active_config.workspace = None
            active_config.save()
        self._cmd.update_prompt()

    # Enable Workspace
    enable_ws_parser = argparse.ArgumentParser()
    enable_ws_parser.add_argument("workspace_name", type=str, help="Workspace")

    @cmd2.as_subcommand_to(
        "workspace", "enable", enable_ws_parser, help="enable a workspace"
    )
    def enable_ws(self, args: argparse.Namespace):
        """Enable Workspace"""
        workspace_name = args.workspace_name
        try:
            self._cmd.api_client.enable_workspace(workspace_name)
        except NotFoundError:
            self._cmd.perror(f"Invalid Workspace: {workspace_name}")
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['check']} "
                    f"Enable workspace: {workspace_name}",
                    fg=COLORS.GREEN,
                )
            )
