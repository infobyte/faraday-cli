import click
from faraday_cli.config import active_config
from tabulate import tabulate


@click.command(help="Show Cli status")
@click.pass_obj
def status(api_client):
    valid_token = api_client.is_token_valid()
    click.secho("Faraday Cli - Status\n", fg="green")
    version = "Unknown"
    if valid_token:
        version_data = api_client.get_version()
        version = f"{version_data['product']}-{version_data['version']}"
    data = [
        {
            "Faraday url": active_config.faraday_url,
            "Verify SSL": active_config.ssl_verify,
            "Version": version,
            "Valid Token": "\U00002714" if valid_token else "\U0000274c",
            "Workspace": active_config.workspace,
        }
    ]
    click.secho(tabulate(data, headers="keys"), fg="green")
