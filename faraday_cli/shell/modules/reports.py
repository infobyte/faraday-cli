from pathlib import Path
import argparse
import getpass

from cmd2 import with_argparser, with_default_category, CommandSet, style
from faraday_cli.config import active_config


@with_default_category("Tools Reports")
class ReportsCommands(CommandSet):
    def __init__(self):
        super().__init__()

    report_parser = argparse.ArgumentParser()
    report_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace"
    )
    report_parser.add_argument(
        "--plugin-id",
        type=str,
        help="Plugin ID (force detection)",
        required=False,
    )
    report_parser.add_argument("report_path", help="Path of the report file")

    @with_argparser(report_parser, preserve_quotes=True)
    def do_process_report(self, args):
        """Process Tool report in Faraday"""
        report_path = Path(args.report_path)
        if not report_path.is_file():
            self._cmd.perror(f"File {report_path} dont exists")
            return
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        if not self._cmd.api_client.is_workspace_valid(workspace_name):
            self._cmd.perror(f"Invalid workspace: {workspace_name}")
            return
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
        self._cmd.poutput(
            style(
                f"{self._cmd.emojis['page']} Processing {plugin.id} report",
                fg="green",
            )
        )
        plugin.processReport(
            report_path.absolute().as_posix(), getpass.getuser()
        )
        self._cmd.data_queue.put(
            {
                "workspace": destination_workspace,
                "json_data": plugin.get_data(),
            }
        )
