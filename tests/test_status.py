import yaml
from click.testing import CliRunner

from faraday_cli.cli.faraday import cli


def test_token_in_status(ok_configuration_file):
    runner = CliRunner()
    cli_execution = runner.invoke(cli, args="status")
    with open(ok_configuration_file.name) as f:
        config_data = yaml.load(f, Loader=yaml.FullLoader)
    assert cli_execution.exit_code == 0
    assert config_data["auth"]["token"][:10] in cli_execution.output
