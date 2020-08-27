"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import tempfile
import os
import json
import pytest
from faraday_cli.api_client import FaradayApi
from flask.testing import FlaskClient
from flask_principal import identity_changed, Identity
from sqlalchemy import event
from requests import Session

from faraday.server.app import create_app
from faraday.server.models import db


TEST_BASE = os.path.abspath(os.path.dirname(__file__))
TEST_DATA = os.path.join(TEST_BASE, "data")

FARADAY_USER = os.getenv("FARADAY_USER")
FARADAY_EMAIL = os.getenv("FARADAY_EMAIL")
FARADAY_PASSWORD = os.getenv("FARADAY_PASSWORD")
FARADAY_URL = os.getenv("FARADAY_URL")

TEMPORATY_SQLITE = tempfile.NamedTemporaryFile()
CONFIG_FILE = f"{os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()))}.yml"
os.environ['FARADAY_CLI_CONFIG'] = CONFIG_FILE
TOKEN = None


@pytest.fixture
def faraday_url():
    return FARADAY_URL

@pytest.fixture
def faraday_user():
    return FARADAY_USER

@pytest.fixture
def faraday_password():
    return FARADAY_PASSWORD

@pytest.fixture(scope="function")
def token():
    global TOKEN
    if not TOKEN:
        api_client = FaradayApi(FARADAY_URL, ssl_verify=False)
        token = api_client.get_token(FARADAY_USER, FARADAY_PASSWORD)
        TOKEN = token
    return TOKEN


@pytest.fixture()
def ok_configuration_file(token):
    with open(CONFIG_FILE, "w") as file:
        with open(os.path.join(TEST_DATA, "config_file_template.yml")) as f:
            template = f.read()
        file.write(template.format(**{'url': FARADAY_URL,'token': token}))
        file.seek(0)
        yield file
    os.remove(CONFIG_FILE)

