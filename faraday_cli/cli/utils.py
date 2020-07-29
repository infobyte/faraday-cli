import os
import click
import yaml
from validators import url


def validate_url(ctx, param, value):
    valid_url = url(value)
    if valid_url:
        return value
    else:
        raise click.BadParameter(f'Invalid url: {value}')
