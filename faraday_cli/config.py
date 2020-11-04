import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_FILE = os.environ.get(
    "FARADAY_CLI_CONFIG", "~/.faraday-cli.yml"
)


class Config:
    def __init__(self):
        self.config_file = Path(os.path.expanduser(DEFAULT_CONFIG_FILE))
        self.faraday_url = None
        self.token = None
        self.ignore_ssl = False
        self.workspace = None

    def load(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                config_data = yaml.load(f, Loader=yaml.FullLoader)
            self.faraday_url = config_data["auth"]["faraday_url"]
            self.token = config_data["auth"]["token"]
            self.ignore_ssl = config_data["auth"]["ignore_ssl"]
            self.workspace = config_data["workbench"]["workspace"]

    def save(self):
        config_data = {
            "auth": {
                "faraday_url": self.faraday_url,
                "token": self.token,
                "ignore_ssl": self.ignore_ssl,
            },
            "workbench": {"workspace": self.workspace},
        }
        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f)


active_config = Config()
