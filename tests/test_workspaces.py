from click.testing import CliRunner

from faraday_cli.cli.faraday import cli


def test_run_without_auth():
    runner = CliRunner()
    asd = runner.invoke(cli, args=" workspace -h")
    assert asd.exit_code != 0
    assert "run \'faraday-cli auth\' first" in asd.output


def test_run_with_token(ok_configuration_file):
    runner = CliRunner()
    asd = runner.invoke(cli, args=" workspace -h")
    assert asd.exit_code != 0
    assert "run \'faraday-cli auth\' first" in asd.output
