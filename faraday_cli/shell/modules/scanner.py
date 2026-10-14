import json
import argparse
from collections import OrderedDict

import click
import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.config import active_config
from faraday_cli.shell.modules.cloud_agent_common import (
    _agent_param_specs,
    is_interactive,
    launch_cloud_agent_and_report,
    print_run_oneliner,
    prompt_params_wizard,
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
        # Params: the union of the input schema (`params`, where mandatory
        # inputs like `target` live) and the configured values
        # (`parameters_data`). Same list the run wizard prompts for.
        specs = _agent_param_specs(self._cmd.api_client, args.scanner_id)
        if specs:
            self._cmd.poutput("\nParameters (pass with --param KEY=VALUE):")
            rows = [
                OrderedDict(
                    {
                        "PARAM": s["name"],
                        "REQUIRED": "yes" if s["mandatory"] else "",
                        "TYPE/DESC": s["description"],
                        "DEFAULT": "" if s["default"] in (None, "") else str(s["default"]),
                    }
                )
                for s in specs
            ]
            self._cmd.poutput(tabulate(rows, headers="keys", tablefmt="simple"))

    # ---- scanners run ----
    run_scanner_parser = argparse.ArgumentParser()
    # Agent can be given positionally (`scanners run first-scan`) or via -a; the
    # positional form is the simple default. One of the two must be present.
    run_scanner_parser.add_argument(
        "agent_pos",
        nargs="?",
        default=None,
        metavar="AGENT",
        help="Cloud-agent id or name/slug (e.g. first-scan). Same as -a.",
    )
    run_scanner_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
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
    run_scanner_parser.add_argument(
        "--wizard",
        action="store_true",
        help="Force the interactive parameter wizard even if --param was given",
    )

    @cmd2.as_subcommand_to("scanners", "run", run_scanner_parser, help="run any cloud agent (scanner)")
    def run_scanner(self, args: argparse.Namespace):
        """Launch any cloud agent against the given workspace(s) with arbitrary params.

        If no ``--param`` / ``--params-json`` is given on an interactive
        terminal, an interactive wizard lists the agent's accepted parameters
        (name, description, default, required) and prompts for each — so the
        user never has to guess the field names. ``--wizard`` forces it. After
        launching, a copy-pasteable one-liner is printed to reproduce the run
        non-interactively next time.
        """
        api_client = self._cmd.api_client

        agent_ref = args.agent or getattr(args, "agent_pos", None)
        if not agent_ref:
            self._cmd.perror(
                "Which scanner? Pass it positionally or with -a, e.g. "
                "'scanners run first-scan'. See 'scanners list'."
            )
            return

        agent_id = resolve_cloud_agent(self._cmd, api_client, agent_ref)
        if agent_id is None:
            return

        # Params. Precedence: --params-json > --param > interactive wizard.
        # The wizard runs when nothing was passed and we're on a real terminal
        # (or when --wizard is explicit); otherwise an empty param set is kept
        # (back-compat for scripted/non-interactive callers).
        run_args = None
        if args.params_json and not args.wizard:
            try:
                run_args = json.loads(args.params_json)
            except ValueError as e:
                self._cmd.perror(f"--params-json is not valid JSON: {e}")
                return
            if not isinstance(run_args, dict):
                self._cmd.perror("--params-json must be a JSON object")
                return
        elif args.param and not args.wizard:
            try:
                run_args = _parse_params(args.param)
            except ValueError as e:
                self._cmd.perror(str(e))
                return
        elif args.wizard or is_interactive():
            run_args = prompt_params_wizard(self._cmd, api_client, agent_id, agent_ref)
            if run_args is None:
                # No param metadata to drive the wizard — fall back to --param.
                try:
                    run_args = _parse_params(args.param)
                except ValueError as e:
                    self._cmd.perror(str(e))
                    return
        else:
            run_args = {}

        workspaces = self._resolve_run_workspaces(args, run_args)
        if workspaces is None:
            return

        self._cmd.poutput(
            cmd2.style(
                f"Launching cloud agent {agent_ref}\n"
                f"  Workspaces: {', '.join(workspaces)}\n"
                f"  Params:     {run_args or '(none)'}",
                fg=COLORS.GREEN,
            )
        )
        launch_cloud_agent_and_report(self._cmd, api_client, agent_id, run_args, workspaces, "Run", args.watch)
        print_run_oneliner(self._cmd, agent_ref, workspaces, run_args)

    # Cloud agents whose run reads the workspace from an arg (e.g. First Scan's
    # ``workspaces``) rather than needing a separate --workspace. The run body
    # ALWAYS carries a workspace list though, so we reconcile the two: whichever
    # the user gave populates both, and they never have to enter it twice.
    _WORKSPACE_PARAM_KEYS = ("workspaces", "workspace", "WORKSPACES", "WORKSPACE_NAME")

    def _resolve_run_workspaces(self, args, run_args):
        """Return the workspace list for the run body, or None after erroring.

        Priority: ``--workspace`` → active connection workspace → a
        workspace-ish param the user already filled (so the wizard's
        ``workspaces`` answer counts) → interactive prompt. Also back-fills the
        agent's own workspace param from the resolved value so First Scan & co
        get it without the user typing it twice.
        """
        if args.workspace:
            workspaces = list(args.workspace)
        elif active_config.workspace:
            workspaces = [active_config.workspace]
        else:
            from_param = next((run_args[k] for k in self._WORKSPACE_PARAM_KEYS if run_args.get(k)), None)
            if from_param:
                workspaces = [w.strip() for w in str(from_param).split(",") if w.strip()]
            elif is_interactive():
                ans = (click.prompt("Workspace", default="", show_default=False) or "").strip()
                workspaces = [w.strip() for w in ans.split(",") if w.strip()]
            else:
                workspaces = []

        if not workspaces:
            self._cmd.perror(
                "No workspace — pass --workspace <name>, select an active workspace, "
                "or set the agent's workspace parameter."
            )
            return None

        # Back-fill the agent's own workspace param so it isn't asked twice.
        for k in self._WORKSPACE_PARAM_KEYS:
            if k in run_args and not run_args.get(k):
                run_args[k] = ",".join(workspaces)
        return workspaces
