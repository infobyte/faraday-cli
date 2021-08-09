import argparse
import json
import os
import time
from pathlib import Path
import urllib.parse

import click
import cmd2
from tabulate import tabulate

from faraday_cli.api_client.filter import FaradayFilter
from faraday_cli.extras.halo.halo import Halo
from faraday_cli.config import active_config
from faraday_cli.shell.utils import IGNORE_SEVERITIES, SEVERITIES


@cmd2.with_default_category("Executive Reports")
class ExecutiveReportsCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    list_templates_parser = argparse.ArgumentParser()
    list_templates_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace name"
    )
    list_templates_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to(
        "executive_report",
        "list-templates",
        list_templates_parser,
        help="list executive reports templates",
    )
    def list_executive_reports_templates(self, args):
        """List executive report templates"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name

        templates_data = self._cmd.api_client.get_executive_report_templates(
            workspace_name
        )
        data = []
        for template in sorted(templates_data["items"], key=lambda x: x[1]):
            data.append({"NAME": template[1], "GROUPED": template[0]})
        self._cmd.poutput(
            tabulate(
                data,
                headers="keys",
                tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                if args.pretty
                else "simple",
            )
        )

    report_parser = argparse.ArgumentParser()
    report_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace name"
    )
    report_parser.add_argument(
        "-t", "--template", type=str, help="Template to use", required=False
    )
    report_parser.add_argument(
        "--title", type=str, help="Report title", default=""
    )
    report_parser.add_argument(
        "--summary", type=str, help="Report summary", default=""
    )
    report_parser.add_argument(
        "--enterprise", type=str, help="Enterprise name", default=""
    )
    report_parser.add_argument(
        "--confirmed", action="store_true", help="Confirmed vulnerabilities"
    )
    report_parser.add_argument(
        "--severity",
        type=str,
        help=f"Filter by severity {'/'.join(SEVERITIES)}",
        default=[],
        nargs="*",
    )
    report_parser.add_argument(
        "--ignore-info",
        action="store_true",
        help=f"Ignore {'/'.join(IGNORE_SEVERITIES)} vulnerabilities",
    )
    report_parser.add_argument(
        "-d", "--destination", type=str, help="Report destination"
    )

    @cmd2.as_subcommand_to(
        "executive_report",
        "create",
        report_parser,
        help="create an executive report",
    )
    def generate_executive_report(self, args):
        """Generate executive report"""

        @Halo(
            text="Generating executive report",
            text_color="green",
            spinner="dots",
        )
        def get_report(report_data, _output):
            report_id = self._cmd.api_client.generate_executive_report(
                workspace_name, report_data
            )
            report_status = "processing"
            while report_status == "processing":
                time.sleep(2)
                report_status = (
                    self._cmd.api_client.get_executive_report_status(
                        workspace_name, report_id
                    )
                )

            else:
                if report_status == "created":
                    download_response = (
                        self._cmd.api_client.download_executive_report(
                            workspace_name, report_id
                        )
                    )
                    report_file = download_response.headers["x-filename"]
                    if _output:
                        output = Path(_output)
                        if output.is_absolute() and not output.is_dir():
                            output_file = _output
                        else:
                            if output.is_dir():
                                output_file = output / report_file
                            else:
                                output_file = Path(os.getcwd()) / _output
                    else:
                        output_file = Path(os.getcwd()) / report_file
                    with open(output_file, "wb") as f:
                        f.write(download_response.body)
                    return output_file
                else:
                    self._cmd.perror("Error generating executive report")

        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        templates_data = self._cmd.api_client.get_executive_report_templates(
            workspace_name
        )
        report_name = "_".join(
            filter(None, [workspace_name, args.title, args.enterprise])
        )
        if not args.template:
            data = []
            template_index = 0
            templates_choices = {}
            for _template in sorted(
                templates_data["items"], key=lambda x: x[1]
            ):
                template_index += 1
                templates_choices[str(template_index)] = _template
                data.append(
                    {
                        "TEMPLATE": template_index,
                        "NAME": _template[1],
                        "GROUPED": _template[0],
                    }
                )
            self._cmd.poutput(
                tabulate(
                    data,
                    headers="keys",
                    tablefmt="simple",
                )
            )
            selected_template = click.prompt(
                "Select your template:",
                type=click.Choice(templates_choices.keys()),
            )
            template = templates_choices[selected_template][1]
            grouped = templates_choices[selected_template][0]
        else:
            templates = {
                template[1]: template[0]
                for template in templates_data["items"]
            }
            if args.template not in templates:
                self._cmd.perror(f"Invalid template: {args.template}")
                return
            else:
                grouped = templates[args.template]
                template = args.template
        report_data = {
            "conclusions": "",
            "confirmed": args.confirmed,
            "enterprise": args.enterprise,
            "grouped": grouped,
            "name": report_name,
            "objectives": "",
            "recommendations": "",
            "scope": "",
            "summary": args.summary,
            "tags": [],
            "template_name": template,
            "title": args.title,
            "vuln_count": 0,
        }
        if args.severity and args.ignore_info:
            self._cmd.perror("Use either --ignore-info or --severity")
            return
        query_filter = FaradayFilter()
        selected_severities = set(map(lambda x: x.lower(), args.severity))
        if selected_severities:
            for severity in selected_severities:
                if severity not in SEVERITIES:
                    self._cmd.perror(f"Invalid severity: {severity}")
                    return
                else:
                    query_filter.require_severity(severity)
        if args.ignore_info:
            for severity in IGNORE_SEVERITIES:
                query_filter.ignore_severity(severity)
        if args.confirmed:
            query_filter.filter_confirmed()
        report_data["filter"] = urllib.parse.quote(
            json.dumps(query_filter.get_filter())
        )
        report_file = get_report(report_data, args.destination)
        self._cmd.poutput(f"Report generated: {report_file}")
