"""Shared helpers for Faraday **cloud agents** (the ``v3/cloud_agents`` API).

Cloud agents are the server-side "scanners" (distinct from the local Faraday
Agents / runners on ``v3/agents``). Both the generic ``scanners`` command group
and the FaradAI-specific ``faradai`` command group launch cloud-agent runs, so
the launch + watch logic lives here once instead of being copied into each
module.
"""

import json
import shlex
import sys
import time
from collections import OrderedDict

import click
import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate
from simple_rest_client.exceptions import NotFoundError


def resolve_cloud_agent(cmd, api_client, ident):
    """Resolve a cloud agent by numeric id or by name/slug substring.

    ``ident`` may be an int-like id (used as-is) or a case-insensitive
    name/slug fragment. Returns the agent id, or ``None`` after a ``perror``
    when nothing matches or the fragment is ambiguous (a table is printed so
    the user can pick an explicit id).
    """
    ident = str(ident).strip()
    agents = api_client.list_cloud_agents() or []

    if ident.isdigit():
        wanted = int(ident)
        for a in agents:
            if a.get("id") == wanted:
                return wanted
        # Not in the list (stale/typo) — still allow the run to try the id so
        # the server gives the authoritative 404, rather than guessing here.
        return wanted

    needle = ident.lower()
    matches = [a for a in agents if needle in f"{a.get('name') or ''} {a.get('slug') or ''}".lower()]
    if not matches:
        cmd.perror(f"No cloud agent matching '{ident}' — run 'scanners list' to see them")
        return None
    if len(matches) > 1:
        cmd.perror(f"'{ident}' matches multiple cloud agents — pass --agent <id>:")
        data = [OrderedDict({"ID": a.get("id"), "NAME": a.get("name"), "SLUG": a.get("slug")}) for a in matches]
        cmd.poutput(tabulate(data, headers="keys", tablefmt="simple"))
        return None
    return matches[0].get("id")


def launch_cloud_agent_and_report(cmd, api_client, agent_id, run_args, workspaces, verb, watch):
    """Run a cloud agent, print the resulting command ids, optionally watch.

    ``verb`` is the word used in the success line ("Scan" / "Triage" / "Run").
    CloudAgent run returns ``{'command_ids': [{'id': N}], 'cam_execution':
    {...}, 'cam_status': 200}``.
    """
    try:
        response = api_client.run_cloud_agent(agent_id, run_args, workspaces)
    except NotFoundError:
        cmd.perror("Cloud agent not found")
        return
    except Exception as e:
        cmd.perror(str(e))
        return

    command_ids = [c.get("id") for c in (response.get("command_ids") or []) if c.get("id") is not None]
    if command_ids:
        cmd.poutput(
            cmd2.style(
                f"{verb} launched. Command id(s): {', '.join(str(c) for c in command_ids)}",
                fg=COLORS.GREEN,
            )
        )
    else:
        cmd.poutput(cmd2.style(f"{verb} launched.", fg=COLORS.GREEN))
        cmd.poutput(json.dumps(response, indent=2))

    if watch:
        watch_commands(cmd, api_client, workspaces[0], command_ids)


def watch_commands(cmd, api_client, workspace_name, command_ids):
    """Poll each command's status until it leaves the running state.

    Uses the already-exposed command listing on the workspace (no new server
    endpoint). If the API client has no command getter, print the ids and a
    follow-up hint rather than inventing an endpoint.
    """
    getter = getattr(api_client, "get_workspace_commands", None) or getattr(api_client, "get_commands", None)
    if getter is None or not command_ids:
        cmd.poutput(
            cmd2.style(
                "--watch: no command-status endpoint available in this CLI; " "check the run in the Faraday UI.",
                fg=COLORS.YELLOW,
            )
        )
        return

    pending = set(command_ids)
    cmd.poutput(cmd2.style("Watching run (Ctrl-C to stop watching)…", fg=COLORS.CYAN))
    try:
        while pending:
            time.sleep(15)
            try:
                commands = getter(workspace_name) or []
            except Exception as e:
                cmd.perror(f"watch: {e}")
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
                    cmd.poutput(cmd2.style(f"  command {cid} finished", fg=COLORS.GREEN))
                    pending.discard(cid)
        cmd.poutput(cmd2.style("Run finished.", fg=COLORS.GREEN))
    except KeyboardInterrupt:
        cmd.poutput(
            cmd2.style(
                "\nStopped watching (run keeps running server-side).",
                fg=COLORS.YELLOW,
            )
        )


# ---------------------------------------------------------------------------
# Interactive param wizard + reproducible one-liner
# ---------------------------------------------------------------------------


def _coerce_value(v):
    """Light type coercion matching scanner._parse_params (int / bool / str)."""
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return v


def _agent_param_specs(api_client, agent_id):
    """Return an ordered list of ``{name, description, default, mandatory}`` for
    a cloud agent's accepted run parameters.

    Reads the richer ``parameters_data`` metadata when present (dict keyed by
    param name), falling back to the flat ``params`` name list. Returns an
    empty list when the agent exposes no parameter metadata (the caller then
    skips the wizard rather than guessing field names).
    """
    try:
        agent = api_client.get_cloud_agent(agent_id) or {}
    except Exception:
        return []
    pdata = agent.get("parameters_data")
    specs = []
    if isinstance(pdata, dict) and pdata:
        for name, meta in pdata.items():
            meta = meta if isinstance(meta, dict) else {}
            specs.append(
                {
                    "name": name,
                    "description": meta.get("description") or meta.get("help") or "",
                    "default": meta.get("base", meta.get("default")),
                    "mandatory": bool(meta.get("mandatory") or meta.get("required")),
                }
            )
    else:
        for name in agent.get("params") or []:
            specs.append({"name": name, "description": "", "default": None, "mandatory": False})
    return specs


def prompt_params_wizard(cmd, api_client, agent_id, agent_label):
    """Interactively collect run params for a cloud agent.

    Lists the agent's accepted parameters (name, description, default, whether
    it's required) and prompts for each. Empty input keeps the default (or
    skips an optional param). Returns a ``{KEY: value}`` dict, or ``None`` if
    the agent exposes no parameter metadata to drive the wizard.

    Only meant for an interactive TTY — callers guard on ``is_interactive()``.
    """
    specs = _agent_param_specs(api_client, agent_id)
    if not specs:
        cmd.poutput(
            cmd2.style(
                f"'{agent_label}' exposes no parameter metadata — " "pass --param KEY=VALUE explicitly.",
                fg=COLORS.YELLOW,
            )
        )
        return None

    cmd.poutput(cmd2.style(f"\nParameters for {agent_label} (Enter = keep default/skip):", fg=COLORS.CYAN))
    out = {}
    for spec in specs:
        name = spec["name"]
        req = " [required]" if spec["mandatory"] else ""
        desc = f" — {spec['description']}" if spec["description"] else ""
        cmd.poutput(cmd2.style(f"  {name}{req}{desc}", fg=COLORS.BLUE))
        default = spec["default"]
        while True:
            raw = click.prompt(
                f"    {name}",
                default="" if default in (None, "") else str(default),
                show_default=default not in (None, ""),
            )
            raw = (raw or "").strip()
            if not raw:
                if spec["mandatory"] and default in (None, ""):
                    cmd.poutput(cmd2.style("    (required — please enter a value)", fg=COLORS.YELLOW))
                    continue
                if default not in (None, ""):
                    out[name] = _coerce_value(default)
                break
            out[name] = _coerce_value(raw)
            break
    return out


def is_interactive():
    """True when stdin+stdout are a real terminal (so prompting makes sense)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def build_run_oneliner(agent_ref, workspaces, params):
    """Build the copy-pasteable ``scanners run`` command that reproduces a run.

    ``agent_ref`` is whatever the user passed (id or name); workspaces and
    params are rendered as ``-w`` / ``--param KEY=VALUE`` tokens, shell-quoted
    so values with spaces/specials paste back cleanly.
    """
    parts = ["faraday-cli", "scanners", "run", "--agent", shlex.quote(str(agent_ref))]
    for ws in workspaces or []:
        parts += ["-w", shlex.quote(str(ws))]
    for key, value in (params or {}).items():
        parts += ["--param", shlex.quote(f"{key}={value}")]
    return " ".join(parts)


def print_run_oneliner(cmd, agent_ref, workspaces, params):
    """Print the reproducible one-liner after a launch."""
    cmd.poutput(cmd2.style("\nReproduce this run with:", fg=COLORS.CYAN))
    cmd.poutput("  " + build_run_oneliner(agent_ref, workspaces, params))
