import json
import argparse
import time
from collections import OrderedDict

import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError

from faraday_cli.config import active_config

# Default pentest instruction when the user doesn't pass --instruction. Mirrors
# the operator's canonical FaradAI cloud-agent run.
DEFAULT_INSTRUCTION = (
    "Full web/API pentest: auth, IDOR/BOLA, SQLi, injection, XSS, SSRF, "
    "mass assignment, JWT. Validate and chain real exploits."
)


def _find_faradai_agent(cmd):
    """Return the single FaradAI cloud-agent dict, or None (after perror).

    Cloud-agent dicts expose ``id``/``name``/``slug`` (no ``active``/``status``/
    ``executors``). Match ``faradai`` case-insensitively on name or slug. Zero
    matches → perror + None; multiple → print an id/name table + None so the
    user can disambiguate with ``--agent-id``.
    """
    agents = cmd.api_client.list_cloud_agents() or []
    matches = [
        a
        for a in agents
        if "faradai" in str(a.get("name") or "").lower() or "faradai" in str(a.get("slug") or "").lower()
    ]
    if not matches:
        cmd.perror("No FaradAI cloud agent found on this server")
        return None
    if len(matches) > 1:
        cmd.perror("Multiple FaradAI cloud agents found — pass --agent-id <id>:")
        data = [OrderedDict({"ID": a.get("id"), "NAME": a.get("name"), "SLUG": a.get("slug")}) for a in matches]
        cmd.poutput(tabulate(data, headers="keys", tablefmt="simple"))
        return None
    return matches[0]


@cmd2.with_default_category("FaradAI")
class FaradaiCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    # ---- faradai list ----
    list_faradai_parser = argparse.ArgumentParser()
    list_faradai_parser.add_argument("-j", "--json-output", action="store_true", help="Show output in json")
    list_faradai_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @cmd2.as_subcommand_to("faradai", "list", list_faradai_parser, help="list cloud agents (FaradAI)")
    def list_cloud_agents(self, args: argparse.Namespace):
        """List cloud agents available on the server."""
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
        self._cmd.poutput(
            tabulate(
                data,
                headers="keys",
                tablefmt="psql" if args.pretty else "simple",
            )
        )

    # ---- faradai scan ----
    scan_parser = argparse.ArgumentParser()
    scan_parser.add_argument("--target", type=str, required=True, help="URL/host to scan")
    scan_parser.add_argument(
        "-w",
        "--workspace",
        action="append",
        type=str,
        help="Workspace name (repeatable); defaults to the active workspace",
    )
    scan_parser.add_argument(
        "--instruction",
        type=str,
        default=DEFAULT_INSTRUCTION,
        help="Pentest instruction for the agent",
    )
    scan_parser.add_argument(
        "--mode",
        type=str,
        choices=["Dual", "Claude", "Codex"],
        default="Dual",
        help="Execution mode (default: Dual)",
    )
    scan_parser.add_argument("--rounds", type=int, default=40, help="Max agent rounds (default: 40)")
    scan_parser.add_argument(
        "--agent-id",
        type=int,
        default=None,
        help="Explicit cloud-agent id (skips FaradAI auto-discovery)",
    )
    scan_parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll the launched command(s) until they finish",
    )

    @cmd2.as_subcommand_to("faradai", "scan", scan_parser, help="run a FaradAI pentest scan")
    def scan(self, args: argparse.Namespace):
        """Launch a FaradAI cloud-agent pentest against a target."""
        # Resolve the agent id (explicit flag, else auto-discover FaradAI).
        if args.agent_id is not None:
            agent_id = args.agent_id
        else:
            agent = _find_faradai_agent(self._cmd)
            if agent is None:
                return
            agent_id = agent.get("id")

        # Resolve workspace(s): explicit --workspace, else the active one.
        if args.workspace:
            workspaces = args.workspace
        elif active_config.workspace:
            workspaces = [active_config.workspace]
        else:
            self._cmd.perror("No active Workspace")
            return

        scan_args = {
            "TARGET": args.target,
            "INSTRUCTION": args.instruction,
            "MODE": args.mode,
            "ROUNDS": args.rounds,
        }

        self._cmd.poutput(
            cmd2.style(
                f"Launching FaradAI scan\n"
                f"  Target:     {args.target}\n"
                f"  Mode:       {args.mode}\n"
                f"  Rounds:     {args.rounds}\n"
                f"  Workspaces: {', '.join(workspaces)}",
                fg=COLORS.GREEN,
            )
        )

        try:
            response = self._cmd.api_client.run_cloud_agent(agent_id, scan_args, workspaces)
        except NotFoundError:
            self._cmd.perror("Cloud agent not found")
            return
        except Exception as e:
            self._cmd.perror(str(e))
            return

        # CloudAgent run returns {'command_ids': [{'id': N}], 'cam_execution':
        # {...}, 'cam_status': 200}.
        command_ids = [c.get("id") for c in (response.get("command_ids") or []) if c.get("id") is not None]
        if command_ids:
            self._cmd.poutput(
                cmd2.style(
                    f"Scan launched. Command id(s): {', '.join(str(c) for c in command_ids)}",
                    fg=COLORS.GREEN,
                )
            )
        else:
            self._cmd.poutput(cmd2.style("Scan launched.", fg=COLORS.GREEN))
            self._cmd.poutput(json.dumps(response, indent=2))

        if args.watch:
            self._watch_commands(workspaces[0], command_ids)

    def _watch_commands(self, workspace_name, command_ids):
        """Poll each command's status until it leaves the running state.

        Uses the already-exposed command listing on the workspace (no new
        server endpoint). If the API client has no command getter, print the
        ids and a follow-up hint rather than inventing an endpoint.
        """
        getter = getattr(self._cmd.api_client, "get_workspace_commands", None) or getattr(
            self._cmd.api_client, "get_commands", None
        )
        if getter is None or not command_ids:
            self._cmd.poutput(
                cmd2.style(
                    "--watch: no command-status endpoint available in this CLI; " "check the run in the Faraday UI.",
                    fg=COLORS.YELLOW,
                )
            )
            return

        pending = set(command_ids)
        self._cmd.poutput(cmd2.style("Watching scan (Ctrl-C to stop watching)…", fg=COLORS.CYAN))
        try:
            while pending:
                time.sleep(15)
                try:
                    commands = getter(workspace_name) or []
                except Exception as e:
                    self._cmd.perror(f"watch: {e}")
                    return
                by_id = {c.get("_id") or c.get("id"): c for c in commands}
                for cid in list(pending):
                    cmd_row = by_id.get(cid)
                    if cmd_row is None:
                        continue
                    # A finished command has a duration / end_date set.
                    if cmd_row.get("duration") not in (
                        None,
                        "",
                        "In progress",
                    ) or cmd_row.get("end_date"):
                        self._cmd.poutput(cmd2.style(f"  command {cid} finished", fg=COLORS.GREEN))
                        pending.discard(cid)
            self._cmd.poutput(cmd2.style("Scan finished.", fg=COLORS.GREEN))
        except KeyboardInterrupt:
            self._cmd.poutput(
                cmd2.style(
                    "\nStopped watching (scan keeps running server-side).",
                    fg=COLORS.YELLOW,
                )
            )
