import argparse
import shlex
import sys

from faraday_cli.shell.shell import FaradayShell

_EPILOG = """\
Run `faraday-cli` with no command to open the interactive shell, or pass a
command directly. `faraday-cli help` lists every command and
`faraday-cli help <command>` shows a command's options
(e.g. `faraday-cli help scanners run`).

Common commands:
  auth       list|use|rm       Connect to a Faraday server / manage sessions
  workspace  list|select|...   Manage workspaces
  pentest    --target <url>    Run a FaradAI pentest (= faradai scan)
  triage     -w <workspace>    Run a FaradAI triage   (= faradai triage)
  scanner    list|get|run      Security scanners / cloud agents (v3/cloud_agents)
                               (aliases: scanners)
  runner     list|get|run      Local Faraday agents / runners   (v3/agents)
                               (aliases: agent, agents, runners)
  vuln | host | service        Query a workspace's data
  tool run | report            Run a tool / import a report

Examples:
  faraday-cli auth
  faraday-cli pentest --target https://example.com
  faraday-cli pentest --target https://example.com --advanced --watch
  faraday-cli scanner list
  faraday-cli scanner run first-scan                 # guided: prompts params
  faraday-cli scanner run first-scan -w my_ws        # no prompts
  faraday-cli scanner run faradai -w my_ws --param TARGET=https://example.com
  faraday-cli triage -w my_ws --severities critical,high --reproduce

Tip: `scanner run <name>` with no params opens a guided prompt that lists the
scanner's fields (so you never have to guess them) and prints a reusable
one-liner afterwards. Agent name goes positionally — `-a` is optional.

No Faraday server connected? The first `pentest`/`triage` walks you through
creating a FaradAI-scan SaaS account and switches to it (see `auth list`).
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="faraday-cli",
        description="Faraday CLI — drive Faraday from the command line.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    command_help = "optional command to run, " "if no command given, enter an interactive shell"
    parser.add_argument("command", nargs="?", help=command_help)
    arg_help = "optional arguments for command"
    parser.add_argument("command_args", nargs=argparse.REMAINDER, help=arg_help)

    args = parser.parse_args(argv)
    app = FaradayShell()
    sys_exit_code = 0
    if args.command:
        # we have a command, run it and then exit. shlex.quote each token so an
        # argument the OS shell already de-quoted (e.g. --agent "First Scan")
        # survives cmd2's own re-parse of this reassembled string — otherwise
        # the space splits it into two args and argparse rejects the tail.
        # A single argument is the whole command line in one string (e.g.
        # `faraday-cli "workspace list"`): pass it as-is, quoting it would turn
        # it into one unknown token that gets run in the system shell.
        if args.command_args:
            command_string = " ".join(shlex.quote(a) for a in [args.command, *args.command_args])
        else:
            command_string = args.command
        app.onecmd_plus_hooks(command_string)
    else:
        # we have no command, drop into shell mode
        app.shell_mode = True
        sys_exit_code = app.cmdloop()
    sys.exit(sys_exit_code)


if __name__ == "__main__":
    main()
