import pytest


@pytest.mark.parametrize(
    "command,subcommand",
    [("workspace", "list"), ("vuln", "list"), ("host", "list"), ("service", "list")],
)
def test_subcommands_are_registered(faraday_cli_app_no_config, command, subcommand):
    # cmd2 >= 3.0 does not load the CommandSets by default (auto_load_commands)
    out = faraday_cli_app_no_config.app_cmd(f"{command} {subcommand} -h")
    assert "invalid choice" not in out.stderr
