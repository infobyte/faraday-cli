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


def _server_error_message(exc):
    """Pull the server's JSON ``message`` out of a simple_rest_client error.

    These exceptions stringify to a huge Response dump; the operator only cares
    about the server's own message (e.g. "Cloud Agent Manager server is not
    available."). Falls back to the exception's own text when unavailable.
    """
    resp = getattr(exc, "response", None)
    body = getattr(resp, "body", None)
    if isinstance(body, dict) and body.get("message"):
        status = getattr(resp, "status_code", None)
        return f"Server error{f' ({status})' if status else ''}: {body['message']}"
    return str(exc).split(",")[0] or str(exc)


def launch_cloud_agent_and_report(cmd, api_client, agent_id, run_args, workspaces, verb, watch):
    """Run a cloud agent, print the resulting command ids, optionally watch.

    ``verb`` is the word used in the success line ("Scan" / "Triage" / "Run").
    CloudAgent run returns ``{'command_ids': [{'id': N}], 'cam_execution':
    {...}, 'cam_status': 200}``.
    """
    try:
        response = api_client.run_cloud_agent(agent_id, run_args, workspaces)
    except NotFoundError:
        cmd.perror(
            "Not found — the agent id or one of the workspaces doesn't exist on "
            "this server (check 'workspace list')."
        )
        return
    except Exception as e:
        cmd.perror(_server_error_message(e))
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


# ``base`` in a cloud-agent param schema is a TYPE placeholder ("string" /
# "url" / "integer" / "boolean"), not a real default value — never pre-fill a
# prompt with it.
_TYPE_PLACEHOLDERS = {"string", "url", "integer", "boolean", "list"}


def _clean_default(value):
    """Normalize a stored default for display/prompting: lists → comma string,
    bools → 'true'/'false', type placeholders / empties → None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        joined = ",".join(str(v).strip() for v in value if str(v).strip())
        return joined or None
    if isinstance(value, str) and value.strip().lower() in _TYPE_PLACEHOLDERS:
        return None
    return value


# Workspace isn't an executor run-arg — it's the run body's top-level
# ``workspaces`` list. Never prompt for it as a param or send it inside ``args``
# (handled separately by the workspace resolution).
_WORKSPACE_KEYS = {"workspaces", "workspace", "WORKSPACES", "WORKSPACE_NAME"}


def _agent_param_specs(api_client, agent_id):
    """Return the executor **run-argument** specs for a cloud agent.

    A Faraday cloud agent exposes two different things:

    * ``params`` — the executor's run INPUT schema: ``{name: {base, type,
      mandatory}}`` (or a flat name list). These are the ONLY keys the run
      ``args`` may contain — the server rejects anything else ("X not
      recognized as an executor argument"). Mandatory inputs like First Scan's
      ``target`` live here.
    * ``parameters_data`` — the agent's CONFIGURED values (resolve_hostname,
      tags, the default workspace…). These are agent config applied
      server-side, NOT run args, so they are used only to seed defaults for
      matching schema params — never prompted or sent on their own.

    Workspace keys are excluded (they go in the run body's top-level
    ``workspaces`` list, not ``args``). Returns [] when the agent exposes no
    input schema (the caller then falls back to explicit ``--param``).
    """
    try:
        agent = api_client.get_cloud_agent(agent_id) or {}
    except Exception:
        return []
    schema = agent.get("params")
    stored = agent.get("parameters_data")
    stored = stored if isinstance(stored, dict) else {}

    specs = []
    if isinstance(schema, dict):
        for name, meta in schema.items():
            if name in _WORKSPACE_KEYS:
                continue
            meta = meta if isinstance(meta, dict) else {}
            specs.append(
                {
                    "name": name,
                    "description": meta.get("description") or meta.get("type") or "",
                    # A real stored value beats the type placeholder in ``base``.
                    "default": _clean_default(stored.get(name, meta.get("base"))),
                    "mandatory": bool(meta.get("mandatory") or meta.get("required")),
                }
            )
    elif isinstance(schema, list):
        for name in schema:
            if name in _WORKSPACE_KEYS:
                continue
            specs.append(
                {
                    "name": name,
                    "description": "",
                    "default": _clean_default(stored.get(name)),
                    "mandatory": False,
                }
            )
    else:
        # No input schema at all — best-effort fall back to configured values
        # (minus workspace) so the wizard still has something to drive on.
        for name, value in stored.items():
            if name in _WORKSPACE_KEYS:
                continue
            specs.append({"name": name, "description": "", "default": _clean_default(value), "mandatory": False})

    return specs


def agent_default_workspaces(api_client, agent_id):
    """The agent's configured default workspace(s) from ``parameters_data`` —
    used to pre-fill the workspace prompt. Returns a list (possibly empty)."""
    try:
        agent = api_client.get_cloud_agent(agent_id) or {}
    except Exception:
        return []
    stored = agent.get("parameters_data") or {}
    for key in _WORKSPACE_KEYS:
        val = stored.get(key)
        if isinstance(val, (list, tuple)):
            out = [str(v).strip() for v in val if str(v).strip()]
            if out:
                return out
        elif isinstance(val, str) and val.strip():
            return [w.strip() for w in val.split(",") if w.strip()]
    return []


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
