"""The agent/scanner command groups accept singular/plural + old/new spellings.

Local Faraday Agents (runners) canonicalise to `agent`; cloud agents (scanners)
canonicalise to `scanners`. These aliases are registered in FaradayShell.__init__
so users don't have to remember the exact one.
"""


def test_runner_aliases_point_to_agent(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    for name in ("agents", "runner", "runners"):
        assert app.aliases.get(name) == "agent", name


def test_scanner_alias_points_to_scanners(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    assert app.aliases.get("scanner") == "scanners"


def test_faradai_shortcuts(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    assert app.aliases.get("pentest") == "faradai scan"
    assert app.aliases.get("triage") == "faradai triage"


def test_canonical_commands_exist(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    # The alias targets must be real commands.
    assert "do_agent" in dir(app)
    assert "do_scanners" in dir(app)
    assert "do_faradai" in dir(app)


def test_auth_session_subcommands_exist(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    # bare `auth` logs in; list/use/rm manage named sessions.
    out = app.app_cmd("help auth")
    text = (out.stdout or "") + (out.stderr or "")
    assert "list" in text and "use" in text and "rm" in text


def test_reload_api_client_exists(faraday_cli_app_no_config):
    app = faraday_cli_app_no_config
    assert hasattr(app, "reload_api_client")
    # No active connection in the no-config fixture → builds an anonymous client.
    app.reload_api_client()
    assert app.api_client is not None


def test_shell_construction_ignores_cli_args(monkeypatch):
    """`faraday-cli <cmd> -h` must not make cmd2 intercept -h at construction.

    allow_cli_args=False stops cmd2 from parsing sys.argv in __init__ (which
    otherwise printed its transcript-test help and exited). main.py parses the
    CLI itself, so constructing the shell with `-h` in argv must NOT SystemExit.
    """
    monkeypatch.setattr("sys.argv", ["faraday-cli", "auth", "-h"])
    from faraday_cli.shell.shell import FaradayShell

    app = FaradayShell()  # must not raise SystemExit
    assert app is not None
