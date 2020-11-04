from collections import defaultdict
import click
import dateutil.parser
from datetime import datetime
from faraday_cli.utils.termgraph import termgraph
from faraday_cli.config import active_config
from faraday_cli.utils.halo.halo import Halo


@click.command(help="Faraday Stats")
@click.option(
    "-ws", "--workspace-name", type=str, help="Name of the workspace"
)
@click.option(
    "-t",
    "--stat-type",
    type=click.Choice(["severity", "vulns", "date"], case_sensitive=False),
    required=True,
)
@click.pass_obj
def stats(api_client, workspace_name, stat_type):
    @Halo(text="Gathering data", text_color="green", spinner="dots")
    def gather_vulns_stats():
        vulns = api_client.get_vulns(workspace)
        if vulns["vulnerabilities"]:
            counters = defaultdict(int)
            for vuln in vulns["vulnerabilities"]:
                if len(vuln["value"]["hostnames"]):
                    host_identifier = vuln["value"]["hostnames"][0]
                else:
                    host_identifier = vuln["value"]["target"]
                counters[host_identifier] += 1
            data = list(map(lambda x: [x], counters.values()))
            termgraph_data = termgraph.TERMGRAPH_DATA_TEMPLATE.copy()
            termgraph_data["title"] = f"Vulnerability stats [{workspace_name}]"
            termgraph_data["data"] = data
            termgraph_data["labels"] = [x for x in counters.keys()]
            termgraph_data["categories"] = ["vulns"]
            termgraph_data["color"] = ["red"]
            return termgraph_data
        else:
            return None

    @Halo(text="Gathering data", text_color="green", spinner="dots")
    def gather_severity_stats():
        vulns = api_client.get_vulns(workspace)
        if vulns["vulnerabilities"]:
            severities_colors = {
                "info": "blue",
                "low": "green",
                "med": "yellow",
                "high": "red",
                "critical": "magenta",
            }
            counters = defaultdict(
                lambda: {"severity": {x: 0 for x in severities_colors}}
            )
            for vuln in vulns["vulnerabilities"]:
                if vuln["value"]["severity"] not in severities_colors:
                    continue
                if len(vuln["value"]["hostnames"]):
                    host_identifier = vuln["value"]["hostnames"][0]
                else:
                    host_identifier = vuln["value"]["target"]
                counters[host_identifier]["severity"][
                    vuln["value"]["severity"]
                ] += 1
            data = list(
                map(lambda x: list(x["severity"].values()), counters.values())
            )
            termgraph_data = termgraph.TERMGRAPH_DATA_TEMPLATE.copy()
            termgraph_data["title"] = f"Severity stats [{workspace_name}]"
            termgraph_data["data"] = data
            termgraph_data["labels"] = [x for x in counters.keys()]
            termgraph_data["categories"] = list(severities_colors.keys())
            termgraph_data["color"] = list(severities_colors.values())
            termgraph_data["stacked"] = True
            return termgraph_data
        else:
            return None

    @Halo(text="Gathering data", text_color="green", spinner="dots")
    def gather_history_stats():
        vulns = api_client.get_vulns(workspace)
        if vulns["vulnerabilities"]:
            counters = defaultdict(int)
            DATE_FORMAT = "%Y-%m-%d"
            min_date = datetime.now()
            for vuln in vulns["vulnerabilities"]:
                vuln_date = dateutil.parser.parse(
                    vuln["value"]["metadata"]["create_time"]
                )
                if vuln_date.date() < min_date.date():
                    min_date = vuln_date
                date_str = vuln_date.strftime(DATE_FORMAT)
                counters[date_str] += 1
            data = list(map(lambda x: [x], counters.values()))
            termgraph_data = termgraph.TERMGRAPH_DATA_TEMPLATE.copy()
            min_date_str = min_date.strftime(DATE_FORMAT)
            title = f"Heatmap since {min_date_str} [{workspace_name}]"
            termgraph_data["title"] = title
            termgraph_data["data"] = data
            termgraph_data["labels"] = [x for x in counters.keys()]
            termgraph_data["start_dt"] = min_date.strftime(DATE_FORMAT)
            termgraph_data["calendar"] = True
            return termgraph_data
        else:
            return None

    def graph_stats(gather_data_func):
        args_data = gather_data_func()
        if args_data:
            _, labels, data, colors = termgraph.read_data(args_data)
            if args_data["calendar"]:
                termgraph.calendar_heatmap(data, labels, args_data)
            else:
                termgraph.chart(colors, data, args_data, labels)
        else:
            click.secho(f"No data in workspace {workspace_name}", fg="red")

    if workspace_name:
        if not api_client.is_workspace_valid(workspace_name):
            click.secho(f"Invalid workspace: {workspace_name}", fg="red")
            return
        else:
            workspace = workspace_name
    else:
        if not active_config.workspace:
            click.secho("No workspace selected", fg="red")
            return
        else:
            workspace = active_config.workspace
    gather_data_function_choices = {
        "severity": gather_severity_stats,
        "vulns": gather_vulns_stats,
        "date": gather_history_stats,
    }
    graph_stats(gather_data_function_choices[stat_type])
