from unittest.mock import MagicMock, patch

from cmd2 import CommandResult

from faraday_cli.config import active_config


def test_ignore_ssl_saved_from_interactive_prompt(faraday_cli_app_no_config):
    """Regression: ignore_ssl set via interactive prompt must be persisted to config."""
    mock_api_instance = MagicMock()
    mock_api_instance.login.return_value = True
    mock_api_instance.get_token.return_value = "test-token"

    prompt_values = {
        "\nFaraday url": "https://faraday.example.com",
        "\nValidate SSL certificate for [https://faraday.example.com]": "N",
        "\nUser": "testuser",
        "\nPassword": "testpass",
    }

    def mock_prompt(text, **kwargs):
        for key, value in prompt_values.items():
            if key in text:
                return value
        return ""

    with patch("faraday_cli.shell.shell.FaradayApi", return_value=mock_api_instance), patch(
        "faraday_cli.shell.shell.click.prompt", side_effect=mock_prompt
    ), patch("faraday_cli.shell.utils.validate_url", side_effect=lambda url: url), patch.object(active_config, "save"):
        faraday_cli_app_no_config.app_cmd("auth")

    assert active_config.ignore_ssl is True


def test_ignore_ssl_false_when_user_validates_cert(faraday_cli_app_no_config):
    """When user chooses to validate SSL (Y), ignore_ssl must be saved as False."""
    mock_api_instance = MagicMock()
    mock_api_instance.login.return_value = True
    mock_api_instance.get_token.return_value = "test-token"

    prompt_values = {
        "\nFaraday url": "https://faraday.example.com",
        "\nValidate SSL certificate for [https://faraday.example.com]": "Y",
        "\nUser": "testuser",
        "\nPassword": "testpass",
    }

    def mock_prompt(text, **kwargs):
        for key, value in prompt_values.items():
            if key in text:
                return value
        return ""

    with patch("faraday_cli.shell.shell.FaradayApi", return_value=mock_api_instance), patch(
        "faraday_cli.shell.shell.click.prompt", side_effect=mock_prompt
    ), patch("faraday_cli.shell.utils.validate_url", side_effect=lambda url: url), patch.object(active_config, "save"):
        faraday_cli_app_no_config.app_cmd("auth")

    assert active_config.ignore_ssl is False


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
