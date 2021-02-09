import tempfile
import os
from pathlib import Path
import cmd2_ext_test
import pytest


TEST_BASE = os.path.abspath(os.path.dirname(__file__))
TEST_DATA = os.path.join(TEST_BASE, "data")

FARADAY_USER = os.getenv("FARADAY_USER")
FARADAY_EMAIL = os.getenv("FARADAY_EMAIL")
FARADAY_PASSWORD = os.getenv("FARADAY_PASSWORD")
FARADAY_URL = os.getenv("FARADAY_URL")

TEMPORATY_SQLITE = tempfile.NamedTemporaryFile()
TEMP_DIR = Path(tempfile.gettempdir())
CONFIG_FILE = f"{TEMP_DIR / next(tempfile._get_candidate_names())}.yml"
os.environ["FARADAY_CLI_CONFIG"] = CONFIG_FILE
TOKEN = None

from faraday_cli.shell.shell import FaradayShell  # noqa: E402
from faraday_cli.api_client import FaradayApi  # noqa: E402
from faraday_cli.config import active_config  # noqa: E402


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
        api_client = FaradayApi(FARADAY_URL, ignore_ssl=False)
        api_client.login(FARADAY_USER, FARADAY_PASSWORD)
        token = api_client.get_token()
        TOKEN = token
    return TOKEN


@pytest.fixture(scope="function")
def ok_configuration_file(token):
    with open(CONFIG_FILE, "w") as file:
        with open(os.path.join(TEST_DATA, "config_file_template.yml")) as f:
            template = f.read()
        config_data = template.format(**{"url": FARADAY_URL, "token": token})
        file.write(config_data)
        file.seek(0)
        active_config.load()
        yield file
    os.remove(CONFIG_FILE)


class FaradayCliAppTester(cmd2_ext_test.ExternalTestMixin, FaradayShell):
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)


@pytest.fixture
def faraday_cli_app_no_config():
    app = FaradayCliAppTester()
    app.fixture_setup()
    yield app
    app.fixture_teardown()


@pytest.fixture
def faraday_cli_app(ok_configuration_file):
    app = FaradayCliAppTester()
    app.fixture_setup()
    yield app
    app.fixture_teardown()
