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
    agent_default_workspaces,
    is_interactive,
    launch_cloud_agent_and_report,
    print_run_oneliner,
    prompt_params_wizard,
    resolve_cloud_agent,
    unknown_run_args,
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
        # Params: the executor's run-input schema (`params`) — the only keys a
        # run's `args` may carry. Config-only fields in `parameters_data`
        # (resolve_hostname, tags) and the workspace are excluded. Same list
        # the run wizard prompts for.
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

        # Fail fast on keys the executor schema doesn't accept — the server
        # would reject the whole run naming only the first bad key. Config
        # fields (resolve_hostname, ignore_info, tags…) live on the agent, not
        # the run.
        unknown = unknown_run_args(api_client, agent_id, run_args)
        if unknown:
            specs = _agent_param_specs(api_client, agent_id)
            accepted = ", ".join(s["name"] for s in specs) or "(none)"
            self._cmd.perror(
                f"Not executor argument(s) for this scanner: {', '.join(unknown)}.\n"
                f"  Accepted --param keys: {accepted}\n"
                "  Other fields are agent configuration — set them on the agent "
                "(Faraday web UI), not per run."
            )
            return

        workspaces = self._resolve_run_workspaces(args, run_args, api_client, agent_id)
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
        launched = launch_cloud_agent_and_report(
            self._cmd, api_client, agent_id, run_args, workspaces, "Run", args.watch
        )
        if launched:
            print_run_oneliner(self._cmd, agent_ref, workspaces, run_args)

    # Workspace goes in the run body's top-level ``workspaces`` list — NOT in
    # ``args`` (the server rejects it as an executor argument). It is resolved
    # on its own and never mixed into the param dict.
    _WORKSPACE_PARAM_KEYS = ("workspaces", "workspace", "WORKSPACES", "WORKSPACE_NAME")

    def _resolve_run_workspaces(self, args, run_args, api_client=None, agent_id=None):
        """Return the workspace list for the run body, or None after erroring.

        Priority: ``--workspace`` → active connection workspace → a
        workspace-ish param the user explicitly passed via ``--param`` → an
        interactive prompt pre-filled with the agent's configured default
        workspace. A workspace key that leaked into ``run_args`` (e.g. an
        explicit ``--param workspaces=…``) is popped out so it never ships
        inside ``args`` — UNLESS the agent's executor input schema declares
        that key as a real run arg (FaradAI triage's ``WORKSPACES`` is a
        required input): then the value is read for the top-level workspace
        resolution but kept in ``args`` too.
        """
        # Keys the executor's own schema declares are real run args, not leaks.
        declared: set = set()
        if api_client is not None and agent_id is not None:
            declared = {s["name"] for s in _agent_param_specs(api_client, agent_id)}
        # Pull any workspace value out of run_args (removing it unless declared).
        from_param = None
        for k in self._WORKSPACE_PARAM_KEYS:
            if k in run_args:
                val = run_args[k] if k in declared else run_args.pop(k)
                if val and from_param is None:
                    from_param = val

        if args.workspace:
            workspaces = list(args.workspace)
        elif active_config.workspace:
            workspaces = [active_config.workspace]
        elif from_param:
            workspaces = [w.strip() for w in str(from_param).split(",") if w.strip()]
        elif is_interactive():
            default_ws = ""
            if api_client is not None and agent_id is not None:
                configured = agent_default_workspaces(api_client, agent_id)
                default_ws = configured[0] if configured else ""
            ans = (click.prompt("Workspace", default=default_ws, show_default=bool(default_ws)) or "").strip()
            workspaces = [w.strip() for w in ans.split(",") if w.strip()]
        else:
            workspaces = []

        if not workspaces:
            self._cmd.perror("No workspace — pass --workspace <name> or select an active workspace.")
            return None
        return workspaces
