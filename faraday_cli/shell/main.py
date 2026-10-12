import argparse
import sys

from faraday_cli.shell.shell import FaradayShell

_EPILOG = """\
Run `faraday-cli` with no command to open the interactive shell, or pass a
command directly. `faraday-cli help` lists every command and
`faraday-cli help <command>` shows a command's options
(e.g. `faraday-cli help scanners run`).

Common commands:
  auth                         Connect to a Faraday server
  workspace list|select|...    Manage workspaces
  pentest   --target <url>     Run a FaradAI pentest (= faradai scan)
  triage    -w <workspace>     Run a FaradAI triage   (= faradai triage)
  scanners  list|get|run       Cloud agents / security scanners (v3/cloud_agents)
  agent     list|get|run       Local Faraday agents / runners   (also: runners)
  vuln | host | service        Query a workspace's data
  tool run | report            Run a tool / import a report

Examples:
  faraday-cli auth
  faraday-cli pentest --target https://example.com
  faraday-cli pentest --target https://example.com --advanced --watch
  faraday-cli scanners list
  faraday-cli scanners run --agent faradai -w my_ws --param TARGET=https://example.com
  faraday-cli triage -w my_ws --severities critical,high --reproduce

No Faraday server? `pentest`/`triage` fall back to the FaradAI-scan SaaS and walk
you through creating an account on first use.
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
        # we have a command, run it and then exit
        command_string = f"{args.command} {' '.join(args.command_args)}"
        app.onecmd_plus_hooks(command_string)
    else:
        # we have no command, drop into shell mode
        app.shell_mode = True
        sys_exit_code = app.cmdloop()
    sys.exit(sys_exit_code)


if __name__ == "__main__":
    main()
