import json
import argparse
import time
from collections import OrderedDict

import cmd2
import click
import requests
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


def _find_faradai_agent(cmd, api_client=None, kind="pentest"):
    """Return the single FaradAI cloud-agent dict for ``kind``, or None (perror).

    Cloud-agent dicts expose ``id``/``name``/``slug`` (no ``active``/``status``/
    ``executors``). The server registers two FaradAI cloud agents: pentest
    (name "FaradAI", slug "faradai") and triage (name "FaradAI Triage", slug
    "faradai-triage"). Both contain "faradai", so matching must distinguish by
    the "triage" token: ``kind="triage"`` wants it present, ``kind="pentest"``
    wants it absent — otherwise a pentest lookup would ambiguously match both.

    Zero matches → perror + None; multiple → print an id/name table + None so
    the user can disambiguate with ``--agent-id``. ``api_client`` defaults to
    the connected server's client; the standalone path passes a scan-scoped one.
    """
    client = api_client if api_client is not None else cmd.api_client
    agents = client.list_cloud_agents() or []

    def _is_faradai(a):
        text = f"{a.get('name') or ''} {a.get('slug') or ''}".lower()
        return "faradai" in text

    def _is_triage(a):
        text = f"{a.get('name') or ''} {a.get('slug') or ''}".lower()
        return "triage" in text

    if kind == "triage":
        matches = [a for a in agents if _is_faradai(a) and _is_triage(a)]
        label = "FaradAI Triage"
    else:
        matches = [a for a in agents if _is_faradai(a) and not _is_triage(a)]
        label = "FaradAI"

    if not matches:
        cmd.perror(f"No {label} cloud agent found on this server")
        return None
    if len(matches) > 1:
        cmd.perror(f"Multiple {label} cloud agents found — pass --agent-id <id>:")
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
    scan_parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run against the FaradAI-scan SaaS using the stored faradai_scan credentials",
    )

    @cmd2.as_subcommand_to("faradai", "scan", scan_parser, help="run a FaradAI pentest scan")
    def scan(self, args: argparse.Namespace):
        """Launch a FaradAI cloud-agent pentest against a target."""
        # Pick the API client: standalone → a scan-scoped client built from the
        # stored faradai_scan profile; otherwise the connected Faraday server.
        if args.standalone:
            api_client = self._standalone_client()
            if api_client is None:
                return
        else:
            api_client = self._cmd.api_client

        # Resolve the agent id (explicit flag, else auto-discover FaradAI).
        if args.agent_id is not None:
            agent_id = args.agent_id
        else:
            agent = _find_faradai_agent(self._cmd, api_client)
            if agent is None:
                return
            agent_id = agent.get("id")

        # Resolve workspace(s). Authenticated path: --workspace or the active
        # workspace. Standalone path: --workspace or the user's stored
        # ext_<domain> workspace (from verify) so the SaaS UX needs only
        # --target. Error clearly if neither is available.
        if args.workspace:
            workspaces = args.workspace
        elif not args.standalone and active_config.workspace:
            workspaces = [active_config.workspace]
        elif args.standalone:
            default_ws = self._standalone_default_workspace()
            if not default_ws:
                self._cmd.perror("No workspace stored. Pass --workspace <name> (or re-run 'faradai verify').")
                return
            workspaces = [default_ws]
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

        self._launch_and_report(api_client, agent_id, scan_args, workspaces, "Scan", args.watch)

    def _launch_and_report(self, api_client, agent_id, run_args, workspaces, verb, watch):
        """Run a cloud agent and render the command ids; optionally --watch.

        Shared by `faradai scan` and `faradai triage`. ``verb`` is the word used
        in the success line ("Scan" / "Triage"). CloudAgent run returns
        ``{'command_ids': [{'id': N}], 'cam_execution': {...}, 'cam_status': 200}``.
        """
        try:
            response = api_client.run_cloud_agent(agent_id, run_args, workspaces)
        except NotFoundError:
            self._cmd.perror("Cloud agent not found")
            return
        except Exception as e:
            self._cmd.perror(str(e))
            return

        command_ids = [c.get("id") for c in (response.get("command_ids") or []) if c.get("id") is not None]
        if command_ids:
            self._cmd.poutput(
                cmd2.style(
                    f"{verb} launched. Command id(s): {', '.join(str(c) for c in command_ids)}",
                    fg=COLORS.GREEN,
                )
            )
        else:
            self._cmd.poutput(cmd2.style(f"{verb} launched.", fg=COLORS.GREEN))
            self._cmd.poutput(json.dumps(response, indent=2))

        if watch:
            self._watch_commands(api_client, workspaces[0], command_ids)

    # ---- faradai triage ----
    triage_parser = argparse.ArgumentParser()
    triage_parser.add_argument(
        "-w",
        "--workspace",
        action="append",
        type=str,
        required=True,
        help="Workspace name to triage (repeatable, at least one required)",
    )
    triage_parser.add_argument(
        "--severities",
        type=str,
        default=None,
        help="Comma-separated severities to triage (e.g. critical,high,medium)",
    )
    triage_parser.add_argument(
        "--confirmed-only",
        action="store_true",
        help="Only triage findings already marked confirmed",
    )
    triage_parser.add_argument(
        "--auto-close-fp",
        action="store_true",
        help="Auto-close findings determined to be false positives",
    )
    triage_parser.add_argument(
        "--target-filter",
        type=str,
        default=None,
        help="Only triage findings matching this target/host filter",
    )
    triage_parser.add_argument(
        "--reproduce",
        action="store_true",
        help="Actively re-test (reproduce) each finding against the live target",
    )
    triage_parser.add_argument("--batch-size", type=int, default=None, help="Findings per triage batch")
    triage_parser.add_argument("--rounds", type=int, default=None, help="Max agent rounds")
    triage_parser.add_argument("--goal", type=str, default=None, help="Free-text goal for the triage run")
    triage_parser.add_argument(
        "--agent-id",
        type=int,
        default=None,
        help="Explicit cloud-agent id (skips FaradAI Triage auto-discovery)",
    )
    triage_parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll the launched command(s) until they finish",
    )
    triage_parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run against the FaradAI-scan SaaS using the stored faradai_scan credentials",
    )
    triage_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ask the agent to plan without mutating findings",
    )

    @cmd2.as_subcommand_to("faradai", "triage", triage_parser, help="run a FaradAI triage over workspace findings")
    def triage(self, args: argparse.Namespace):
        """Launch a FaradAI triage cloud-agent run over existing workspace findings."""
        # Pick the API client: standalone → scan-scoped; else connected server.
        if args.standalone:
            api_client = self._standalone_client()
            if api_client is None:
                return
        else:
            api_client = self._cmd.api_client

        # Resolve the triage cloud-agent id (explicit, else auto-discover).
        if args.agent_id is not None:
            agent_id = args.agent_id
        else:
            agent = _find_faradai_agent(self._cmd, api_client, kind="triage")
            if agent is None:
                return
            agent_id = agent.get("id")

        workspaces = args.workspace

        # Pre-flight: triage re-tests EXISTING findings, so a workspace with no
        # vulns has nothing to do. Check each workspace's vuln count up front and
        # refuse to launch when they're all empty (a triage over an empty
        # workspace otherwise spawns a runner that finds nothing — wasted budget
        # + a confusing "Element not found"). Skipped on --dry-run (planning is
        # fine on an empty ws) and when the count can't be fetched (fail-open).
        if not args.dry_run:
            empties, total = [], 0
            for ws in workspaces:
                try:
                    stats = (api_client.get_workspace(ws) or {}).get("stats") or {}
                    n = int(stats.get("total_vulns") or 0)
                except Exception:
                    n = -1  # couldn't fetch → don't block
                if n == 0:
                    empties.append(ws)
                elif n > 0:
                    total += n
            if empties and total == 0:
                self._cmd.perror(
                    "Nothing to triage: workspace(s) "
                    f"{', '.join(empties)} have no findings. Run a scan first "
                    "(faradai scan), or pass --dry-run to plan anyway."
                )
                return

        # WORKSPACES is the mandatory param; its presence is what tells the CAM
        # this is a triage run. Pass as a comma-separated string.
        triage_args = {"WORKSPACES": ",".join(workspaces)}
        if args.severities:
            triage_args["SEVERITIES"] = args.severities
        if args.confirmed_only:
            triage_args["CONFIRMED_ONLY"] = True
        if args.auto_close_fp:
            triage_args["AUTO_CLOSE_FP"] = True
        if args.target_filter:
            triage_args["TARGET_FILTER"] = args.target_filter
        if args.reproduce:
            triage_args["REPRODUCE"] = True
        if args.batch_size is not None:
            triage_args["BATCH_SIZE"] = args.batch_size
        if args.rounds is not None:
            triage_args["ROUNDS"] = args.rounds
        if args.goal:
            triage_args["GOAL"] = args.goal
        if args.dry_run:
            triage_args["DRY_RUN"] = True

        self._cmd.poutput(
            cmd2.style(
                f"Launching FaradAI triage\n"
                f"  Workspaces: {', '.join(workspaces)}\n"
                f"  Severities: {args.severities or 'all'}\n"
                f"  Reproduce:  {args.reproduce}",
                fg=COLORS.GREEN,
            )
        )
        # Triage's own workspace is the first one listed (used by --watch).
        self._launch_and_report(api_client, agent_id, triage_args, workspaces, "Triage", args.watch)

    def _watch_commands(self, api_client, workspace_name, command_ids):
        """Poll each command's status until it leaves the running state.

        Uses the already-exposed command listing on the workspace (no new
        server endpoint). If the API client has no command getter, print the
        ids and a follow-up hint rather than inventing an endpoint.
        """
        getter = getattr(api_client, "get_workspace_commands", None) or getattr(api_client, "get_commands", None)
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

    # ---- faradai register ----
    register_parser = argparse.ArgumentParser()
    register_parser.add_argument("--email", type=str, required=True, help="Email to register")
    register_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Account password (prompted securely if omitted)",
    )
    register_parser.add_argument(
        "--dashboard-url",
        type=str,
        default=None,
        help="FaradAI dashboard URL serving /api/register (default: configured dashboard url, with /_ai)",
    )

    @cmd2.as_subcommand_to("faradai", "register", register_parser, help="register on the FaradAI-scan SaaS")
    def register(self, args: argparse.Namespace):
        """Start a FaradAI-scan registration — emails a verification code."""
        dashboard_url = (args.dashboard_url or active_config.faradai_dashboard_url).rstrip("/")
        password = args.password or click.prompt(
            "Password", hide_input=True, confirmation_prompt=True, show_default=False
        )
        try:
            resp = requests.post(
                f"{dashboard_url}/api/register",
                json={"email": args.email, "password": password},
                timeout=30,
            )
        except requests.RequestException as e:
            self._cmd.perror(f"Could not reach {dashboard_url}: {e}")
            return
        if resp.status_code == 404:
            self._cmd.perror(f"Public registration is not enabled on {dashboard_url}")
            return
        if resp.status_code != 200:
            self._cmd.perror(self._error_message(resp))
            return
        self._cmd.poutput(
            cmd2.style(
                f"Verification code sent to {args.email}.\n" f"Run: faradai verify --email {args.email} --code <code>",
                fg=COLORS.GREEN,
            )
        )

    # ---- faradai verify ----
    verify_parser = argparse.ArgumentParser()
    verify_parser.add_argument("--email", type=str, required=True, help="Email being verified")
    verify_parser.add_argument("--code", type=str, required=True, help="6-digit verification code")
    verify_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Account password (prompted securely if omitted)",
    )
    verify_parser.add_argument(
        "--dashboard-url",
        type=str,
        default=None,
        help="FaradAI dashboard URL serving /api/verify (default: configured dashboard url, with /_ai)",
    )

    @cmd2.as_subcommand_to("faradai", "verify", verify_parser, help="verify a FaradAI-scan registration")
    def verify(self, args: argparse.Namespace):
        """Confirm the emailed code — provisions the account and stores the token."""
        dashboard_url = (args.dashboard_url or active_config.faradai_dashboard_url).rstrip("/")
        password = args.password or click.prompt("Password", hide_input=True, show_default=False)
        try:
            resp = requests.post(
                f"{dashboard_url}/api/verify",
                json={"email": args.email, "code": args.code, "password": password},
                timeout=60,
            )
        except requests.RequestException as e:
            self._cmd.perror(f"Could not reach {dashboard_url}: {e}")
            return
        if resp.status_code == 404:
            self._cmd.perror("No pending registration (or registration disabled). Run 'faradai register' first.")
            return
        if resp.status_code != 200:
            self._cmd.perror(self._error_message(resp))
            return
        data = resp.json() if resp.content else {}
        token = data.get("token")
        if not token:
            self._cmd.perror("Verify succeeded but no token was returned.")
            return
        # verify returns the Faraday *server* URL (faraday_url) for scans/login —
        # distinct from the dashboard URL used for register/verify. It also
        # returns the user's own ext_<domain> workspace, stored as the
        # standalone default so scans need only --target.
        active_config.faradai_scan_url = (data.get("faraday_url") or active_config.faradai_scan_url).rstrip("/")
        active_config.faradai_scan_token = token
        if data.get("workspace"):
            active_config.faradai_scan_workspace = data["workspace"]
        active_config.save()
        self._cmd.poutput(
            cmd2.style(
                "FaradAI scan account ready. Try: faradai scan --target <url> --standalone",
                fg=COLORS.GREEN,
            )
        )

    # ---- faradai login ----
    login_parser = argparse.ArgumentParser()
    login_parser.add_argument("--email", type=str, required=True, help="Account email")
    login_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Account password (prompted securely if omitted)",
    )
    login_parser.add_argument(
        "--scan-url",
        type=str,
        default=None,
        help="FaradAI-scan instance URL (default: configured faradai_scan url)",
    )

    @cmd2.as_subcommand_to("faradai", "login", login_parser, help="log in to the FaradAI-scan SaaS")
    def login(self, args: argparse.Namespace):
        """Re-authenticate an existing FaradAI-scan account (no new OTP)."""
        from faraday_cli.api_client import FaradayApi
        from faraday_cli.api_client.exceptions import InvalidCredentials

        scan_url = (args.scan_url or active_config.faradai_scan_url).rstrip("/")
        password = args.password or click.prompt("Password", hide_input=True, show_default=False)
        api = FaradayApi(scan_url, ignore_ssl=active_config.ignore_ssl)
        try:
            api.login(args.email, password)
            token = api.get_token()
        except InvalidCredentials:
            self._cmd.perror("Invalid credentials")
            return
        except Exception as e:
            self._cmd.perror(f"Login failed: {e}")
            return
        if not token:
            self._cmd.perror("Login did not return a token.")
            return
        active_config.faradai_scan_url = scan_url
        active_config.faradai_scan_token = token
        active_config.save()
        self._cmd.poutput(cmd2.style(f"Logged in to {scan_url}.", fg=COLORS.GREEN))

    def _standalone_client(self):
        """Build a FaradayApi bound to the stored faradai_scan profile, or None.

        Returns None (after perror) when no scan token is stored — the user
        must `faradai register`/`verify` or `faradai login` first.
        """
        from faraday_cli.api_client import FaradayApi

        if not active_config.faradai_scan_token:
            self._cmd.perror("Not registered. Run: faradai register --email <you>")
            return None
        return FaradayApi(
            active_config.faradai_scan_url,
            ignore_ssl=active_config.ignore_ssl,
            token=active_config.faradai_scan_token,
        )

    @staticmethod
    def _standalone_default_workspace():
        """Per-user default workspace for standalone scans.

        Uses the ext_<domain> workspace that `verify` stored in the config.
        Returns None when none is stored (the caller then errors clearly asking
        for --workspace, rather than silently hitting a workspace the user
        can't access).
        """
        return active_config.faradai_scan_workspace

    @staticmethod
    def _error_message(resp):
        """Best-effort human message from a non-2xx FaradAI-scan API response."""
        try:
            payload = resp.json()
            return f"Error ({resp.status_code}): {payload.get('error') or payload}"
        except ValueError:
            return f"Error ({resp.status_code})"
