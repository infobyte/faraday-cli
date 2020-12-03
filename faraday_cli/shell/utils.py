import json
from socket import gethostbyname, inet_aton
import jsonschema

import click
from validators import url

SEVERITY_COLORS = {
    "critical": "magenta",
    "high": "red",
    "med": "yellow",
    "low": "green",
    "info": "blue",
    "unclassified": "cyan",
}


def validate_url(value):
    valid_url = url(value)
    if valid_url:
        return value
    else:
        raise Exception(f"Invalid url: {value}")


def validate_json(ctx, param, value):
    if value:
        try:
            json_value = json.loads(value)
        except Exception as e:
            raise click.BadParameter(
                click.style(f"Invalid json parameter: {value} - {e}", fg="red")
            )
        else:
            return json_value


def json_schema_validator(schema):
    def _validate_json(value):
        if value:
            if isinstance(value, str):
                try:
                    json_value = json.loads(value)
                except Exception as e:
                    raise Exception(f"Invalid json format: {value} - {e}")
            else:
                json_value = value
            try:
                jsonschema.validate(instance=json_value, schema=schema)
            except jsonschema.exceptions.ValidationError as err:
                raise Exception(f"{err}")
            return json_value

    return _validate_json


def get_ip_and_hostname(value):
    try:
        inet_aton(value)
        return value, None
    except Exception:
        try:
            ip_address = gethostbyname(value)
        except OSError:
            return value, None
        else:
            return ip_address, value


def trim_long_text(text, size=50):
    if len(text) <= size:
        return text
    else:
        return f"{text[:size]}..."


def get_severity_color(severity):
    return SEVERITY_COLORS.get(severity, "white")
