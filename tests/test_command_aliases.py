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
