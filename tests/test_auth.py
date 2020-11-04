from click.testing import CliRunner

from faraday_cli.cli.faraday import cli


def test_run_without_auth():
    runner = CliRunner()
    cli_execution = runner.invoke(cli, args="workspace")
    assert cli_execution.exit_code != 0
    assert "run 'faraday-cli auth' first" in cli_execution.output


def test_get_token_with_invalid_credentials(faraday_url, faraday_user):
    runner = CliRunner()
    parameters = [
        "auth",
        "--faraday-url",
        faraday_url,
        "--user",
        faraday_user,
        "--password",
        "PASSWORD",
    ]
    cli_execution = runner.invoke(cli, parameters)
    assert cli_execution.exit_code == 0
    assert "Invalid credentials" in cli_execution.output, cli_execution.output


def test_get_token_with_valid_credentials(
    faraday_url, faraday_user, faraday_password
):
    runner = CliRunner()
    parameters = [
        "auth",
        "--faraday-url",
        faraday_url,
        "--user",
        faraday_user,
        "--password",
        faraday_password,
    ]
    cli_execution = runner.invoke(cli, parameters)
    assert cli_execution.exit_code == 0
    assert "Saving config" in cli_execution.output, cli_execution.output
