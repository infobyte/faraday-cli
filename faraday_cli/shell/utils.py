import json
import os
import getpass
import sys
import subprocess
import shlex
import io
from socket import gethostbyname, inet_aton
import jsonschema

from cmd2 import Fg as COLORS

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
    "critical": COLORS.MAGENTA,
    "high": COLORS.RED,
    "med": COLORS.YELLOW,
    "low": COLORS.GREEN,
    "info": COLORS.BLUE,
    "unclassified": COLORS.CYAN,
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
    return SEVERITY_COLORS.get(severity, COLORS.WHITE)


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


def get_active_workspaces_filter() -> dict:
    query_filter = {"filters": [{"name": "active", "op": "eq", "val": "true"}]}
    return query_filter


def run_tool(plugin, user, command, show_output=True):
    current_path = os.path.abspath(os.getcwd())
    modified_command = plugin.processCommandString(
        getpass.getuser(), current_path, command
    )
    if modified_command:
        command = modified_command
    p = subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = io.StringIO()
    while True:
        retcode = p.poll()
        line = p.stdout.readline().decode("utf-8")
        if show_output:
            sys.stdout.write(line)
        output.write(line)
        if retcode is not None:
            extra_lines = map(
                lambda x: x.decode("utf-8"), p.stdout.readlines()
            )
            if show_output:
                sys.stdout.writelines(line)
            output.writelines(extra_lines)
            break
    output_value = output.getvalue()
    if retcode == 0:
        plugin.processOutput(output_value)
        return plugin.get_data()
    else:
        return None
