from pathlib import Path
import argparse
import getpass
import json

import cmd2
from cmd2 import Fg as COLORS
from faraday_cli.config import active_config


@cmd2.with_default_category("Tools Reports")
class ReportsCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    report_parser = cmd2.Cmd2ArgumentParser()
    report_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace"
    )
    report_parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create the workspace it not exists",
    )
    report_parser.add_argument(
        "--plugin-id",
        type=str,
        help="Plugin ID (force detection)",
        required=False,
    )
    report_parser.add_argument(
        "-j",
        "--json-output",
        action="store_true",
        help="Show output in json (dont send to faraday)",
    )
    report_parser.add_argument(
        "--vuln-tag",
        type=str,
        help="Tag to add to vulnerabilities",
        required=False,
        action="append",
    )
    report_parser.add_argument(
        "--host-tag",
        type=str,
        help="Tag to add to hosts",
        required=False,
        action="append",
    )
    report_parser.add_argument(
        "--service-tag",
        type=str,
        help="Tag to add to services",
        required=False,
        action="append",
    )
    report_parser.add_argument("report_path", help="Path of the report file")

    @cmd2.as_subcommand_to(
        "tool", "report", report_parser, help="process a report from a tool"
    )
    def process_report(self, args: argparse.Namespace):
        """Process Tool report in Faraday"""
        report_path = Path(args.report_path)
        if not report_path.is_file():
            self._cmd.perror(f"File {report_path} dont exists")
            return
        if not args.json_output:
            if not args.workspace_name:
                if active_config.workspace:
                    workspace_name = active_config.workspace
                else:
                    self._cmd.perror("No active Workspace")
                    return
            else:
                workspace_name = args.workspace_name
            if not self._cmd.api_client.is_workspace_available(workspace_name):
                if not args.create_workspace:
                    self._cmd.perror(f"Invalid workspace: {workspace_name}")
                    return
                else:
                    try:
                        self._cmd.api_client.create_workspace(workspace_name)
                        self._cmd.poutput(
                            cmd2.style(
                                f"Workspace {workspace_name} created",
                                fg=COLORS.GREEN,
                            )
                        )
                    except Exception as e:
                        self._cmd.perror(f"Error creating workspace: {e}")
                        return
                    else:
                        destination_workspace = workspace_name
            else:
                destination_workspace = workspace_name
        if args.plugin_id:
            plugin = self._cmd.plugins_manager.get_plugin(args.plugin_id)
            if not plugin:
                self._cmd.perror(f"Invalid Plugin: {args.plugin_id}")
                return
        else:
            plugin = self._cmd.report_analyzer.get_plugin(report_path)
            if not plugin:
                self._cmd.perror(
                    f"{self._cmd.emojis['cross']} "
                    f"Failed to detect report: {report_path}"
                )
                return
        if not args.json_output:
            self._cmd.poutput(
                cmd2.style(
                    f"{self._cmd.emojis['page']} "
                    f"Processing {plugin.id} report",
                    fg=COLORS.GREEN,
                )
            )
        plugin.vuln_tag = args.vuln_tag
        plugin.host_tag = args.host_tag
        plugin.service_tag = args.service_tag
        plugin.processReport(
            report_path.absolute().as_posix(), getpass.getuser()
        )
        if args.json_output:
            self._cmd.poutput(json.dumps(plugin.get_data(), indent=4))
        else:
            self._cmd.data_queue.put(
                {
                    "workspace": destination_workspace,
                    "json_data": plugin.get_data(),
                }
            )
