import json
from socket import gethostbyname, inet_aton
import jsonschema

from validators import url

from .exceptions import InvalidJson, InvalidJsonSchema

IGNORE_SEVERITIES = ("informational", "unclassified")
SEVERITIES = (
    "informational",
    "critical",
    "high",
    "medium",
    "low",
    "unclassified",
)
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


def validate_json(value):
    if value:
        try:
            json_value = json.loads(value)
        except Exception as e:
            raise InvalidJson(f"Invalid json parameter: {value} - {e}")
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
                raise InvalidJsonSchema(f"{err}")
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


def get_ignore_info_severity_filter() -> dict:
    query_filter = {
        "filters": [
            {
                "and": [
                    {"name": "severity", "op": "neq", "val": severity}
                    for severity in IGNORE_SEVERITIES
                ]
            }
        ]
    }
    return query_filter


def get_severity_filter(severities: list) -> dict:
    query_filter = {
        "filters": [
            {
                "or": [
                    {"name": "severity", "op": "eq", "val": severity}
                    for severity in severities
                ]
            }
        ]
    }
    return query_filter


def get_confirmed_filter() -> dict:
    query_filter = {
        "filters": [{"name": "confirmed", "op": "==", "val": "true"}]
    }
    return query_filter
