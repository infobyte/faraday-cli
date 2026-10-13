import argparse
from collections import OrderedDict

import cmd2
from cmd2 import Fg as COLORS
from tabulate import tabulate

from faraday_cli.config import active_config


@cmd2.with_default_category("Authentication")
class AuthSessionCommands(cmd2.CommandSet):
    """Manage named connection sessions under the `auth` command.

    One connection is active at a time; these subcommands list the saved
    connections, switch the active one, and remove them. `auth` with no
    subcommand still logs in to a server (see shell.do_auth).
    """

    def __init__(self):
        super().__init__()

    # ---- auth list ----
    list_auth_parser = argparse.ArgumentParser()
    list_auth_parser.add_argument("-p", "--pretty", action="store_true", help="Show table in a pretty format")

    @cmd2.as_subcommand_to("auth", "list", list_auth_parser, help="list saved connection sessions")
    def list_sessions(self, args: argparse.Namespace):
        """List the saved connection sessions (the active one is marked)."""
        if not active_config.sessions:
            self._cmd.perror("No sessions — run 'auth' to connect, or 'faradai register' for the SaaS")
            return
        data = []
        for name, s in active_config.sessions.items():
            active = name == active_config.active_session
            data.append(
                OrderedDict(
                    {
                        "ACTIVE": "\U00002714" if active else "",
                        "NAME": name,
                        "KIND": s.get("kind") or "server",
                        "SERVER": s.get("faraday_url"),
                        "WORKSPACE": s.get("workspace") or "-",
                    }
                )
            )
        self._cmd.poutput(tabulate(data, headers="keys", tablefmt="psql" if args.pretty else "simple"))

    # ---- auth use ----
    use_auth_parser = argparse.ArgumentParser()
    use_auth_parser.add_argument("name", type=str, help="Session name to make active (see 'auth list')")

    @cmd2.as_subcommand_to("auth", "use", use_auth_parser, help="switch the active connection")
    def use_session(self, args: argparse.Namespace):
        """Switch the active connection to a saved session."""
        if not active_config.use_session(args.name):
            self._cmd.perror(f"No session named '{args.name}'. Run 'auth list' to see the saved ones.")
            return
        # Rebuild the live API client against the newly-active session.
        self._cmd.reload_api_client()
        s = active_config.sessions.get(args.name, {})
        msg = f"Switched to '{args.name}' ({s.get('faraday_url')})"
        if s.get("workspace"):
            msg += f" — workspace {s['workspace']}"
        self._cmd.poutput(cmd2.style(msg, fg=COLORS.GREEN))

    # ---- auth rm ----
    rm_auth_parser = argparse.ArgumentParser()
    rm_auth_parser.add_argument("name", type=str, help="Session name to remove")

    @cmd2.as_subcommand_to("auth", "rm", rm_auth_parser, help="remove a saved connection session")
    def remove_session(self, args: argparse.Namespace):
        """Remove a saved session (clears the active connection if it was active)."""
        was_active = args.name == active_config.active_session
        if not active_config.remove_session(args.name):
            self._cmd.perror(f"No session named '{args.name}'.")
            return
        if was_active:
            # The active connection is gone — point the client at nothing until
            # the user switches or logs in again.
            self._cmd.reload_api_client()
            self._cmd.poutput(
                cmd2.style(
                    f"Removed '{args.name}' (was active — no active connection now; "
                    f"run 'auth use <name>' or 'auth').",
                    fg=COLORS.YELLOW,
                )
            )
        else:
            self._cmd.poutput(cmd2.style(f"Removed '{args.name}'.", fg=COLORS.GREEN))
