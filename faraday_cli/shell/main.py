import argparse
import sys

from faraday_cli.shell.shell import FaradayShell


def main(argv=None):

    parser = argparse.ArgumentParser(description="Commands as arguments")
    command_help = (
        "optional command to run, "
        "if no command given, enter an interactive shell"
    )
    parser.add_argument("command", nargs="?", help=command_help)
    arg_help = "optional arguments for command"
    parser.add_argument(
        "command_args", nargs=argparse.REMAINDER, help=arg_help
    )

    args = parser.parse_args(argv)
    app = FaradayShell()
    sys_exit_code = 0
    if args.command:
        # we have a command, run it and then exit
        command_string = f"{args.command} {' '.join(args.command_args)}"
        app.onecmd_plus_hooks(command_string)
    else:
        # we have no command, drop into interactive mode
        app.run_as_shell = True
        sys_exit_code = app.cmdloop()
    sys.exit(sys_exit_code)


if __name__ == "__main__":
    main()
