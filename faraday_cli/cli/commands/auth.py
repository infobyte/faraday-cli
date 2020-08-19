import click
from faraday_cli.config import active_config
from faraday_cli.api_client import FaradayApi
from faraday_cli.cli import utils
from urllib.parse import urlparse


@click.command(help="Faraday auth configuration")
@click.option(
    "--url", type=str, prompt="Faraday url", callback=utils.validate_url
)
@click.option("--user", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def auth(url, user, password):
    url_data = urlparse(url)
    ssl_verify = False
    if url_data.scheme == "https":
        ssl_verify = (
            click.prompt(
                f"Validate SSL certificate for [{url}]",
                type=click.Choice(choices=["Y", "N"], case_sensitive=False),
                default="Y",
            )
            == "Y"
        )

    api_client = FaradayApi(url, ssl_verify=ssl_verify)
    try:
        token = api_client.get_token(user, password)
        active_config.faraday_url = url
        active_config.ssl_verify = ssl_verify
        active_config.token = token
        active_config.save()
        click.secho("Saving config", fg="green")
    except Exception as e:
        click.secho(f"{e}", fg="red")
