import json
import argparse
from collections import OrderedDict

import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.config import active_config
from faraday_cli.shell.modules.cloud_agent_common import (
    launch_cloud_agent_and_report,
    resolve_cloud_agent,
)


def _parse_params(pairs):
    """Turn ``["KEY=VALUE", ...]`` into a dict, coercing int/bool-ish values.

    Cloud-agent params are strings on the wire, but ROUNDS/booleans read better
    typed; the server validates, so we only do light coercion: a bare integer
    becomes an int, ``true``/``false`` become bools, everything else stays a
    string. ``=`` inside the value is preserved (split once).
    """
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--param must be KEY=VALUE (got '{pair}')")
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"--param has an empty key (got '{pair}')")
        v = value.strip()
        if v.isdigit():
            out[key] = int(v)
        elif v.lower() in ("true", "false"):
            out[key] = v.lower() == "true"
        else:
            out[key] = value
    return out


@cmd2.with_default_category("Scanners")
class ScannerCommands(cmd2.CommandSet):
    """Generic Faraday **cloud agent** (scanner) commands.

    Cloud agents are the server-side scanners on the ``v3/cloud_agents`` API —
    distinct from the local Faraday Agents / runners (``agent`` / ``runners``).
    FaradAI is one such scanner: it can be launched generically here
    (``scanners run --agent faradai ...``) or via its own ``faradai`` command.
    """

    def __init__(self):
        super().__init__()

    # ---- scanners list ----
    list_scanner_parser = argparse.ArgumentParser()
    list_scanner_parser.add_argument("-j", "--json-output", action="store_true", help="Show output in json")
    list_scanner_parser.add_argument("-p", "--pretty", action="store_true", help="Show table in a pretty format")

    @cmd2.as_subcommand_to("scanners", "list", list_scanner_parser, help="list cloud agents (scanners)")
    def list_scanners(self, args: argparse.Namespace):
        """List the cloud agents (scanners) available on the server."""
        agents = self._cmd.api_client.list_cloud_agents()
        if not agents:
            self._cmd.perror("No cloud agents in server")
            return
        if args.json_output:
            self._cmd.poutput(json.dumps(agents, indent=4))
            return
        data = [
            OrderedDict(
                {
                    "ID": x.get("id"),
                    "NAME": x.get("name"),
                    "SLUG": x.get("slug"),
                    "CATEGORY": ", ".join(x.get("category") or []),
                    "LAST_RUN": x.get("last_run"),
                }
            )
            for x in agents
        ]
        self._cmd.poutput(tabulate(data, headers="keys", tablefmt="psql" if args.pretty else "simple"))

    # ---- scanners get ----
    get_scanner_parser = argparse.ArgumentParser()
    get_scanner_parser.add_argument("scanner_id", type=int, help="ID of the cloud agent")
    get_scanner_parser.add_argument("-j", "--json-output", action="store_true", help="Show output in json")
    get_scanner_parser.add_argument("-p", "--pretty", action="store_true", help="Show table in a pretty format")

    @cmd2.as_subcommand_to("scanners", "get", get_scanner_parser, help="get a cloud agent + its params")
    def get_scanner(self, args: argparse.Namespace):
        """Show a cloud agent and the parameters it accepts (for ``scanners run``)."""
        try:
            agent = self._cmd.api_client.get_cloud_agent(args.scanner_id)
        except NotFoundError:
            self._cmd.perror("Cloud agent not found")
            return
        if args.json_output:
            self._cmd.poutput(json.dumps(agent, indent=4))
            return
        head = [
            OrderedDict(
                {
                    "ID": agent.get("id"),
                    "NAME": agent.get("name"),
                    "SLUG": agent.get("slug"),
                    "CATEGORY": ", ".join(agent.get("category") or []),
                    "LAST_RUN": agent.get("last_run"),
                }
            )
        ]
        self._cmd.poutput(tabulate(head, headers="keys", tablefmt="psql" if args.pretty else "simple"))
        # Params: cloud-agent dicts expose the accepted param names under
        # `params` (list) and/or `parameters_data` (richer per-param metadata).
        params = agent.get("params") or list((agent.get("parameters_data") or {}).keys())
        if params:
            self._cmd.poutput("\nParameters (pass with --param KEY=VALUE):")
            self._cmd.poutput("  " + ", ".join(str(p) for p in params))

    # ---- scanners run ----
    run_scanner_parser = argparse.ArgumentParser()
    run_scanner_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        required=True,
        help="Cloud-agent id or name/slug fragment (e.g. 2 or 'faradai')",
    )
    run_scanner_parser.add_argument(
        "-w",
        "--workspace",
        action="append",
        type=str,
        help="Workspace name (repeatable); defaults to the active workspace",
    )
    run_scanner_parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Run parameter (repeatable), e.g. --param TARGET=https://x --param ROUNDS=20",
    )
    run_scanner_parser.add_argument(
        "--params-json",
        type=str,
        default=None,
        help="All run params as a JSON object (alternative to repeated --param)",
    )
    run_scanner_parser.add_argument(
        "--watch", action="store_true", help="Poll the launched command(s) until they finish"
    )

    @cmd2.as_subcommand_to("scanners", "run", run_scanner_parser, help="run any cloud agent (scanner)")
    def run_scanner(self, args: argparse.Namespace):
        """Launch any cloud agent against the given workspace(s) with arbitrary params."""
        api_client = self._cmd.api_client

        agent_id = resolve_cloud_agent(self._cmd, api_client, args.agent)
        if agent_id is None:
            return

        # Params: --params-json takes precedence; else collect repeated --param.
        if args.params_json:
            try:
                run_args = json.loads(args.params_json)
            except ValueError as e:
                self._cmd.perror(f"--params-json is not valid JSON: {e}")
                return
            if not isinstance(run_args, dict):
                self._cmd.perror("--params-json must be a JSON object")
                return
        else:
            try:
                run_args = _parse_params(args.param)
            except ValueError as e:
                self._cmd.perror(str(e))
                return

        # Workspace(s): explicit --workspace, else the active workspace.
        if args.workspace:
            workspaces = args.workspace
        elif active_config.workspace:
            workspaces = [active_config.workspace]
        else:
            self._cmd.perror("No workspace — pass --workspace <name> or select an active workspace")
            return

        self._cmd.poutput(
            cmd2.style(
                f"Launching cloud agent {args.agent}\n"
                f"  Workspaces: {', '.join(workspaces)}\n"
                f"  Params:     {run_args or '(none)'}",
                fg=COLORS.GREEN,
            )
        )
        launch_cloud_agent_and_report(self._cmd, api_client, agent_id, run_args, workspaces, "Run", args.watch)
