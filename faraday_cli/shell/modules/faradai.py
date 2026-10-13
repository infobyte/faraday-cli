import argparse
import secrets
import string
from collections import OrderedDict

import cmd2
import click
import requests
from cmd2 import Fg as COLORS
from tabulate import tabulate

from faraday_cli.api_client.exceptions import InvalidCredentials
from faraday_cli.config import active_config, FARADAI_SCAN_SESSION
from faraday_cli.shell.modules.cloud_agent_common import launch_cloud_agent_and_report
from faraday_cli.shell.modules.faradai_instructions import (
    SCAN_GOALS,
    SCAN_INSTRUCTIONS,
    TRIAGE_INSTRUCTION,
)

# Agent rounds per scan tier. Standard (default) is a quick first scan;
# Advanced goes deeper. --rounds overrides either explicitly.
STANDARD_ROUNDS = 20
ADVANCED_ROUNDS = 80


def _generate_password(length: int = 16) -> str:
    """Generate a strong random password that satisfies the Faraday policy.

    The server requires at least one special character (and a reasonable
    length), so guarantee one special plus a mix of upper/lower/digits.
    """
    specials = "!@#$%^&*-_=+"
    alphabet = string.ascii_letters + string.digits + specials
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in specials for c in pw)
        ):
            return pw


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

    # Listing cloud agents is generic (not FaradAI-specific) — it lives under
    # the `scanners` command group: `scanners list`. `faradai` is FaradAI-only:
    # scan / triage + the FaradAI-scan SaaS onboarding (register/verify/login).

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
        default=None,
        help="Pentest instruction (default: the wizard's staged template for the tier — " "standard or advanced)",
    )
    scan_parser.add_argument(
        "--goal",
        type=str,
        default=None,
        help="Free-text goal/focus for the run (wizard GOAL; empty by default)",
    )
    scan_parser.add_argument(
        "--mode",
        type=str,
        choices=["Dual", "Claude", "Codex"],
        default="Dual",
        help="Execution mode (default: Dual)",
    )
    scan_parser.add_argument(
        "--rounds",
        type=int,
        default=None,
        help=f"Max agent rounds (default: {STANDARD_ROUNDS}; {ADVANCED_ROUNDS} with --advanced)",
    )
    scan_parser.add_argument(
        "--advanced",
        action="store_true",
        help=f"Advanced (deeper) scan — {ADVANCED_ROUNDS} rounds instead of the standard {STANDARD_ROUNDS}",
    )
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
        help="(deprecated) Switch the active connection to the FaradAI-scan SaaS "
        "for this run; prefer 'auth use <name>'",
    )

    @cmd2.as_subcommand_to("faradai", "scan", scan_parser, help="run a FaradAI pentest scan")
    def scan(self, args: argparse.Namespace):
        """Launch a FaradAI cloud-agent pentest against a target."""
        # Single active connection: use whatever you're connected to. --standalone
        # (deprecated) switches the active connection to the FaradAI-scan SaaS; a
        # first-time user with nothing configured is onboarded into the SaaS.
        if args.standalone:
            self._warn_standalone_deprecated()
        if not self._ensure_connected(args.standalone):
            return
        api_client = self._cmd.api_client

        # Resolve the agent id (explicit flag, else auto-discover FaradAI).
        if args.agent_id is not None:
            agent_id = args.agent_id
        else:
            try:
                agent = _find_faradai_agent(self._cmd, api_client)
            except InvalidCredentials:
                self._cmd.perror(
                    "Active connection's credentials are invalid or expired. "
                    "Run 'auth' (or 'faradai login' for the SaaS)."
                )
                return
            if agent is None:
                return
            agent_id = agent.get("id")

        # Resolve workspace(s): --workspace, else the active connection's
        # workspace, else auto-discover when the user can access exactly one.
        if args.workspace:
            workspaces = args.workspace
        elif active_config.workspace:
            workspaces = [active_config.workspace]
        else:
            sole = self._sole_accessible_workspace(api_client)
            if sole:
                workspaces = [sole]
            else:
                self._cmd.perror(
                    "No workspace resolved. Pass --workspace <name> "
                    "(you have access to zero or multiple workspaces)."
                )
                return

        # Tier: --advanced selects the deeper template + 80 rounds; otherwise
        # standard + 20. The tier picks the default INSTRUCTION (the same staged
        # template the wizard sends); an explicit --rounds overrides the count
        # but not the template.
        tier = "advanced" if args.advanced else "standard"
        rounds = args.rounds if args.rounds is not None else (ADVANCED_ROUNDS if args.advanced else STANDARD_ROUNDS)
        rounds_label = "custom" if args.rounds is not None else tier
        instruction = args.instruction or SCAN_INSTRUCTIONS[tier]

        scan_args = {
            "TARGET": args.target,
            "INSTRUCTION": instruction,
            "GOAL": args.goal or SCAN_GOALS[tier],
            "MODE": args.mode,
            "ROUNDS": rounds,
        }

        self._cmd.poutput(
            cmd2.style(
                f"Launching FaradAI scan\n"
                f"  Target:     {args.target}\n"
                f"  Mode:       {args.mode}\n"
                f"  Rounds:     {rounds} ({rounds_label})\n"
                f"  Workspaces: {', '.join(workspaces)}",
                fg=COLORS.GREEN,
            )
        )

        launch_cloud_agent_and_report(self._cmd, api_client, agent_id, scan_args, workspaces, "Scan", args.watch)

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
        "--instruction",
        type=str,
        default=None,
        help="Triage instruction (default: the wizard's staged triage template)",
    )
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
        help="(deprecated) Switch the active connection to the FaradAI-scan SaaS "
        "for this run; prefer 'auth use <name>'",
    )
    triage_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ask the agent to plan without mutating findings",
    )

    @cmd2.as_subcommand_to("faradai", "triage", triage_parser, help="run a FaradAI triage over workspace findings")
    def triage(self, args: argparse.Namespace):
        """Launch a FaradAI triage cloud-agent run over existing workspace findings."""
        # Single active connection (see scan). --standalone (deprecated) switches
        # to the SaaS.
        if args.standalone:
            self._warn_standalone_deprecated()
        if not self._ensure_connected(args.standalone):
            return
        api_client = self._cmd.api_client

        # Resolve the triage cloud-agent id (explicit, else auto-discover).
        if args.agent_id is not None:
            agent_id = args.agent_id
        else:
            try:
                agent = _find_faradai_agent(self._cmd, api_client, kind="triage")
            except InvalidCredentials:
                self._cmd.perror(
                    "Active connection's credentials are invalid or expired. "
                    "Run 'auth' (or 'faradai login' for the SaaS)."
                )
                return
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
        # this is a triage run. The triage cloud agent has NO `INSTRUCTION`
        # param (only scan does) — its guidance channel is `GOAL`, so the
        # default triage brief goes there (overridable with --goal / --instruction).
        triage_args = {
            "WORKSPACES": ",".join(workspaces),
            "GOAL": args.goal or args.instruction or TRIAGE_INSTRUCTION,
        }
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
        launch_cloud_agent_and_report(self._cmd, api_client, agent_id, triage_args, workspaces, "Triage", args.watch)

    # ---- faradai register ----
    register_parser = argparse.ArgumentParser()
    register_parser.add_argument("--email", type=str, required=True, help="Email to register")
    register_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Account password (auto-generated and shown if omitted)",
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
        if not self._do_register(args.email, args.password, dashboard_url):
            return
        self._cmd.poutput(cmd2.style("Run: faradai verify <code>", fg=COLORS.GREEN))

    def _do_register(self, email, password, dashboard_url):
        """POST /api/register; stash email+password; report. Returns True on OK.

        Shared by the `register` command and the guided onboarding. ``password``
        None → generate a strong one and show it. The stash lets a later
        `verify <code>` run without flags.
        """
        generated = password is None
        password = password or _generate_password()
        try:
            resp = requests.post(
                f"{dashboard_url}/api/register",
                json={"email": email, "password": password},
                timeout=30,
            )
        except requests.RequestException as e:
            self._cmd.perror(f"Could not reach {dashboard_url}: {e}")
            return False
        if resp.status_code == 404:
            self._cmd.perror(f"Public registration is not enabled on {dashboard_url}")
            return False
        if resp.status_code != 200:
            self._cmd.perror(self._error_message(resp))
            return False
        active_config.faradai_pending_email = email
        active_config.faradai_pending_password = password
        active_config.save()
        lines = [f"Verification code sent to {email}."]
        if generated:
            lines.append(f"Generated password: {password}  (save it — you'll log in with it later)")
        self._cmd.poutput(cmd2.style("\n".join(lines), fg=COLORS.GREEN))
        return True

    def _guided_onboarding(self):
        """First-time standalone onboarding: register → prompt code → verify.

        Runs when `faradai scan --standalone` finds no stored token. Prompts for
        an email, registers (auto-generating a password), prompts for the
        emailed code, and verifies — leaving a usable token + workspace so the
        caller can proceed with the scan. Returns True on success.
        """
        self._cmd.poutput(cmd2.style("No FaradAI-scan account yet — let's create one.", fg=COLORS.CYAN))
        email = click.prompt("Email")
        dashboard_url = active_config.faradai_dashboard_url.rstrip("/")
        if not self._do_register(email, None, dashboard_url):
            return False
        code = click.prompt("Verification code (check your email)")
        if not self._do_verify(code, email, active_config.faradai_pending_password, dashboard_url):
            return False
        return True

    # ---- faradai verify ----
    verify_parser = argparse.ArgumentParser()
    verify_parser.add_argument(
        "code",
        type=str,
        nargs="?",
        default=None,
        help="6-digit verification code (positional; or use --code)",
    )
    verify_parser.add_argument("--code", dest="code_flag", type=str, default=None, help="6-digit verification code")
    verify_parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Email being verified (default: the pending registration's email)",
    )
    verify_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Account password (default: the pending registration's password)",
    )
    verify_parser.add_argument(
        "--dashboard-url",
        type=str,
        default=None,
        help="FaradAI dashboard URL serving /api/verify (default: configured dashboard url, with /_ai)",
    )

    @cmd2.as_subcommand_to("faradai", "verify", verify_parser, help="verify a FaradAI-scan registration")
    def verify(self, args: argparse.Namespace):
        """Confirm the emailed code — provisions the account and stores the token.

        Usage is just ``faradai verify <code>`` after ``faradai register`` — the
        email and password are taken from the pending registration. Override
        with --email / --password when verifying a registration started
        elsewhere.
        """
        dashboard_url = (args.dashboard_url or active_config.faradai_dashboard_url).rstrip("/")
        code = args.code or args.code_flag
        if not code:
            self._cmd.perror("Missing code. Usage: faradai verify <code>")
            return
        email = args.email or active_config.faradai_pending_email
        if not email:
            self._cmd.perror("No pending email. Pass --email or run 'faradai register' first.")
            return
        # Password: explicit flag → the pending (register-stashed) one → prompt.
        password = args.password or active_config.faradai_pending_password
        if not password:
            password = click.prompt("Password", hide_input=True, show_default=False)
        if self._do_verify(code, email, password, dashboard_url):
            # _do_verify made the SaaS session active — rebuild the live client so
            # this session (and the rest of the CLI) talk to it right away.
            self._cmd.reload_api_client()
            self._cmd.poutput(
                cmd2.style(
                    f"FaradAI scan account ready — active connection is now "
                    f"'{FARADAI_SCAN_SESSION}' ({email}).\n"
                    "Try: faradai scan --target <url>   (or 'auth use <name>' to switch back)",
                    fg=COLORS.GREEN,
                )
            )

    def _do_verify(self, code, email, password, dashboard_url):
        """POST /api/verify; on success store token+url+workspace, clear pending.

        Shared by the `verify` command and the guided onboarding. Returns True
        on success (the caller prints the appropriate next-step message).
        """
        try:
            resp = requests.post(
                f"{dashboard_url}/api/verify",
                json={"email": email, "code": code, "password": password},
                timeout=60,
            )
        except requests.RequestException as e:
            self._cmd.perror(f"Could not reach {dashboard_url}: {e}")
            return False
        if resp.status_code == 404:
            self._cmd.perror("No pending registration (or registration disabled). Run 'faradai register' first.")
            return False
        if resp.status_code != 200:
            self._cmd.perror(self._error_message(resp))
            return False
        data = resp.json() if resp.content else {}
        token = data.get("token")
        if not token:
            self._cmd.perror("Verify succeeded but no token was returned.")
            return False
        # verify returns the Faraday *server* URL (faraday_url) for scans/login —
        # distinct from the dashboard URL used for register/verify. It also
        # returns the user's own ext_<domain> workspace.
        scan_url = (data.get("faraday_url") or active_config.faradai_scan_url).rstrip("/")
        active_config.faradai_scan_url = scan_url
        # Registration is complete — the token is the durable credential now, so
        # drop the transient pending email/password BEFORE saving the session.
        active_config.faradai_pending_email = None
        active_config.faradai_pending_password = None
        # Store the SaaS connection as a session and make it active (auto-switch):
        # a freshly-registered scan user wants to run against the SaaS now, and
        # we don't want two servers "connected" at once.
        active_config.add_session(
            FARADAI_SCAN_SESSION,
            faraday_url=scan_url,
            token=token,
            workspace=data.get("workspace"),
            kind="saas",
            user=email,
            make_active=True,
        )
        return True

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
        # Store the user's ext_<domain> workspace when they have exactly one, so
        # a later `faradai scan` needs only --target. A token-scoped client is
        # used to query it.
        ws = self._sole_accessible_workspace(api)
        # Save the SaaS connection as a session and make it active (auto-switch),
        # same as verify — logging into the SaaS makes it your active connection.
        active_config.add_session(
            FARADAI_SCAN_SESSION,
            faraday_url=scan_url,
            token=token,
            workspace=ws,
            kind="saas",
            user=args.email,
            make_active=True,
        )
        self._cmd.reload_api_client()
        msg = f"Logged in to {scan_url} — active connection is now '{FARADAI_SCAN_SESSION}'."
        if ws:
            msg += f" Workspace: {ws}"
        self._cmd.poutput(cmd2.style(msg, fg=COLORS.GREEN))

    def _warn_standalone_deprecated(self):
        self._cmd.poutput(
            cmd2.style(
                "note: --standalone is deprecated — it now switches your active "
                "connection to the FaradAI-scan SaaS ('auth use "
                f"{FARADAI_SCAN_SESSION}' / 'auth list').",
                fg=COLORS.YELLOW,
            )
        )

    def _ensure_connected(self, force_saas):
        """Ensure there is a usable active connection for scan/triage.

        New single-active-connection model:
          * ``force_saas`` (deprecated ``--standalone``) → make the FaradAI-scan
            SaaS session the active one (switching to it, or onboarding when
            there's none), so the SaaS becomes your active connection.
          * otherwise use whatever connection is active. Only when NOTHING is
            configured at all do we fall into SaaS onboarding for a first-time
            scan-only user.

        Returns True when a usable active connection exists (caller then uses
        ``self._cmd.api_client``), or False if the user aborts onboarding.
        """
        if force_saas:
            return self._activate_saas_session()
        if active_config.active_session:
            return True
        # Nothing configured → first-time scan-only user → SaaS onboarding.
        return self._activate_saas_session()

    def _activate_saas_session(self):
        """Switch the active connection to the FaradAI-scan SaaS (onboard if none).

        Self-healing: an existing SaaS session with a dead token is cleared and
        re-created via onboarding. On success the SaaS session is active and the
        live API client is rebuilt. Returns False if the user aborts onboarding.
        """
        from faraday_cli.api_client import FaradayApi

        sess = active_config.sessions.get(FARADAI_SCAN_SESSION)
        if sess and sess.get("token"):
            client = FaradayApi(
                sess.get("faraday_url"),
                ignore_ssl=bool(sess.get("ignore_ssl")),
                token=sess.get("token"),
            )
            try:
                valid = client.is_token_valid()
            except Exception:
                valid = True  # transient check failure → don't block
            if valid:
                active_config.use_session(FARADAI_SCAN_SESSION)
                self._cmd.reload_api_client()
                return True
            self._cmd.poutput(
                cmd2.style(
                    "Stored FaradAI-scan session is invalid or expired — let's set it up again.",
                    fg=COLORS.YELLOW,
                )
            )
            active_config.remove_session(FARADAI_SCAN_SESSION)

        if not self._guided_onboarding():
            return False
        # _do_verify (called by onboarding) registered + activated the session.
        self._cmd.reload_api_client()
        return True

    @staticmethod
    def _sole_accessible_workspace(api_client):
        """Return the user's workspace name when they can access exactly one.

        A scan user is a pentester scoped to a single ext_<domain> workspace,
        so when the server returns exactly one accessible active workspace we
        can use it as the default (no --workspace needed). Returns None when
        there are zero or many (caller then asks for --workspace) or on error.
        """
        try:
            workspaces = api_client.get_workspaces() or []
        except Exception:
            return None
        names = [w.get("name") for w in workspaces if w.get("name")]
        return names[0] if len(names) == 1 else None

    @staticmethod
    def _error_message(resp):
        """Best-effort human message from a non-2xx FaradAI-scan API response."""
        try:
            payload = resp.json()
            return f"Error ({resp.status_code}): {payload.get('error') or payload}"
        except ValueError:
            return f"Error ({resp.status_code})"
