import click
from faraday_cli.config import active_config
from faraday_cli.api_client import FaradayApi
from faraday_cli.cli import utils
from urllib.parse import urlparse

from simple_rest_client.exceptions import AuthError, ClientError


@click.command(help="Faraday auth configuration")
@click.option("--faraday-url", type=str)
@click.option("--ignore-ssl", is_flag=True)
@click.option("--user", type=str)
@click.option("--password", type=str)
def auth(faraday_url, ignore_ssl, user, password):
    active_config.load()
    if not faraday_url:
        faraday_url = utils.validate_url(
            click.prompt("Faraday url", default=active_config.faraday_url)
        )
        url_data = urlparse(faraday_url)
        if url_data.scheme == "https":
            ignore_ssl = (
                click.prompt(
                    f"Validate SSL certificate for [{faraday_url}]",
                    type=click.Choice(
                        choices=["Y", "N"], case_sensitive=False
                    ),
                    default="Y",
                )
                == "N"
            )
    else:
        faraday_url = utils.validate_url(faraday_url)
    if not user:
        user = click.prompt("User")
    if not password:
        password = click.prompt("Password", hide_input=True)
    api_client = FaradayApi(faraday_url, ignore_ssl=ignore_ssl)
    try:
        token = api_client.get_token(user, password)
        active_config.faraday_url = faraday_url
        active_config.ignore_ssl = ignore_ssl
        active_config.token = token
        active_config.save()
        click.secho("Saving config", fg="green")
    except AuthError:
        click.secho("Invalid credentials", fg="red")
    except ClientError:
        click.secho("Invalid credentials", fg="red")
    except Exception as e:
        click.secho(f"{e}", fg="red")
