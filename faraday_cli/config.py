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
        self.custom_plugins_path = None
        self.ignore_info_severity = False
        self.hostname_resolution = True
        self.auto_command_detection = True
        self.load()

    def config_exists(self) -> bool:
        return self.config_file.exists()

    def load(self):
        try:
            if self.config_exists():
                with open(self.config_file) as f:
                    config_data = yaml.load(f, Loader=yaml.FullLoader)
                self.faraday_url = config_data.get("auth", {}).get(
                    "faraday_url"
                )
                self.token = config_data.get("auth", {}).get("token")
                self.ignore_ssl = config_data.get("auth", {}).get("ignore_ssl")
                self.workspace = config_data.get("faraday", {}).get(
                    "workspace"
                )
                self.custom_plugins_path = config_data.get("settings", {}).get(
                    "custom_plugins_path"
                )
                self.ignore_info_severity = config_data.get(
                    "settings", {}
                ).get("ignore_info_severity", False)
                self.auto_command_detection = config_data.get(
                    "settings", {}
                ).get("auto_command_detection", True)
        except KeyError:
            pass

    def save(self):
        config_data = {
            "auth": {
                "faraday_url": self.faraday_url,
                "token": self.token,
                "ignore_ssl": self.ignore_ssl,
            },
            "faraday": {"workspace": self.workspace},
            "settings": {
                "custom_plugins_path": self.custom_plugins_path,
                "ignore_info_severity": self.ignore_info_severity,
                "auto_command_detection": self.auto_command_detection,
            },
        }
        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f)


active_config = Config()
