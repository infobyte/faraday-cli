import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_FILE = os.environ.get("FARADAY_CLI_CONFIG", "~/.faraday-cli.yml")

# The FaradAI-scan SaaS has TWO distinct endpoints:
#  * the FaradAI dashboard (`/api/register` + `/api/verify`), served under the
#    `/_ai` prefix on the dashboard host — used by `faradai register`/`verify`.
#  * the Faraday server (`/_api/v3/cloud_agents`, `/_api/login`) — used by
#    `faradai scan --standalone` and `faradai login`. `verify` returns this URL
#    as `faraday_url` and the CLI stores it.
DEFAULT_FARADAI_DASHBOARD_URL = "https://faradai-scan.apps.faradaysec.com/_ai"
DEFAULT_FARADAI_SCAN_URL = "https://scan.apps.faradaysec.com"


class Config:
    def __init__(self):
        self.config_file = Path(os.path.expanduser(DEFAULT_CONFIG_FILE))
        self.faraday_url = None
        self.token = None
        self.ignore_ssl = False
        self.workspace = None
        self.custom_plugins_path = None
        self.ignore_info_severity = False
        self.hostname_resolution = False
        self.auto_command_detection = True
        # FaradAI-scan SaaS profile (separate from the main `auth` server so a
        # user can be registered on the public scan instance without touching
        # their primary Faraday connection). dashboard_url serves register/verify
        # (under /_ai); scan_url is the Faraday server for scans/login.
        self.faradai_dashboard_url = DEFAULT_FARADAI_DASHBOARD_URL
        self.faradai_scan_url = DEFAULT_FARADAI_SCAN_URL
        self.faradai_scan_token = None
        self.load()

    def config_exists(self) -> bool:
        return self.config_file.exists()

    def load(self):
        try:
            if self.config_exists():
                with open(self.config_file) as f:
                    config_data = yaml.load(f, Loader=yaml.FullLoader)
                # An empty config file parses to None — treat it as "no config".
                if not config_data:
                    return
                self.faraday_url = config_data.get("auth", {}).get("faraday_url")
                self.token = config_data.get("auth", {}).get("token")
                self.ignore_ssl = config_data.get("auth", {}).get("ignore_ssl")
                self.workspace = config_data.get("faraday", {}).get("workspace")
                self.custom_plugins_path = config_data.get("settings", {}).get("custom_plugins_path")
                self.ignore_info_severity = config_data.get("settings", {}).get("ignore_info_severity", False)
                self.auto_command_detection = config_data.get("settings", {}).get("auto_command_detection", True)
                faradai_scan = config_data.get("faradai_scan", {}) or {}
                self.faradai_dashboard_url = faradai_scan.get("dashboard_url") or DEFAULT_FARADAI_DASHBOARD_URL
                self.faradai_scan_url = faradai_scan.get("url") or DEFAULT_FARADAI_SCAN_URL
                self.faradai_scan_token = faradai_scan.get("token")
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
            "faradai_scan": {
                "dashboard_url": self.faradai_dashboard_url,
                "url": self.faradai_scan_url,
                "token": self.faradai_scan_token,
            },
        }
        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f)


active_config = Config()
