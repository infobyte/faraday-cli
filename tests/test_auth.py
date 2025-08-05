from cmd2 import CommandResult


def test_run_without_auth(faraday_cli_app_no_config):
    out = faraday_cli_app_no_config.app_cmd("status")
    assert isinstance(out, CommandResult)
    assert "Missing Config, run 'faraday-cli auth'" in out.stderr.strip()


def test_auth_with_invalid_credentials(faraday_cli_app_no_config, faraday_url):
    command = f"auth -f {faraday_url} -u wrong_user -p wrong_password"
    out = faraday_cli_app_no_config.app_cmd(command)
    assert isinstance(out, CommandResult)
    assert out.stderr.strip() == "Invalid credentials"


def test_auth_with_valid_credentials(faraday_cli_app_no_config, faraday_url, faraday_user, faraday_password):
    command = f"auth -f {faraday_url} -u {faraday_user} -p {faraday_password}"
    out = faraday_cli_app_no_config.app_cmd(command)
    assert isinstance(out, CommandResult)
    assert "Saving config" in out.stdout.strip()
