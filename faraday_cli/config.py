import os
import yaml
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_CONFIG_FILE = os.environ.get("FARADAY_CLI_CONFIG", "~/.faraday-cli.yml")

# The FaradAI-scan SaaS has TWO distinct endpoints:
#  * the FaradAI dashboard (`/api/register` + `/api/verify`), served under the
#    `/_ai` prefix on the dashboard host — used by `faradai register`/`verify`.
#  * the Faraday server (`/_api/v3/cloud_agents`, `/_api/login`) — used by
#    `faradai scan` and `faradai login`. `verify` returns this URL as
#    `faraday_url` and the CLI stores it as the `faradai-scan` session.
DEFAULT_FARADAI_DASHBOARD_URL = "https://faradai-scan.apps.faradaysec.com/_ai"
DEFAULT_FARADAI_SCAN_URL = "https://scan.apps.faradaysec.com"

# Session name used for the FaradAI-scan SaaS connection created by
# `faradai register`/`verify`/`login`.
FARADAI_SCAN_SESSION = "faradai-scan"


class Config:
    """CLI configuration with named connection sessions.

    There is exactly ONE active connection at a time (``active_session``); the
    flat ``faraday_url``/``token``/``ignore_ssl``/``workspace`` attributes mirror
    it so every command keeps reading the active connection unchanged. Other
    connections (e.g. your corporate Faraday plus the FaradAI-scan SaaS) are kept
    in ``sessions`` so you can switch between them with ``auth use <name>``
    instead of being connected to two servers at once.
    """

    def __init__(self):
        self.config_file = Path(os.path.expanduser(DEFAULT_CONFIG_FILE))
        # Flat view of the ACTIVE session (source of truth while running).
        self.faraday_url = None
        self.token = None
        self.ignore_ssl = False
        self.workspace = None
        # Named connection registry: {name: {faraday_url, token, ignore_ssl,
        # workspace, kind}}. kind is "server" or "saas".
        self.sessions = {}
        self.active_session = None
        self.custom_plugins_path = None
        self.ignore_info_severity = False
        self.hostname_resolution = False
        self.auto_command_detection = True
        # FaradAI-scan SaaS endpoints + in-flight registration transients. The
        # SaaS *connection* itself is stored as the `faradai-scan` session; these
        # fields are the register/verify endpoints and the pending email/password
        # stashed by `faradai register` (cleared on a successful verify).
        self.faradai_dashboard_url = DEFAULT_FARADAI_DASHBOARD_URL
        self.faradai_scan_url = DEFAULT_FARADAI_SCAN_URL
        self.faradai_pending_email = None
        self.faradai_pending_password = None
        self.load()

    def config_exists(self) -> bool:
        return self.config_file.exists()

    # -- session helpers ----------------------------------------------------

    def _sync_from_session(self, name):
        """Copy a session's connection fields into the flat active view."""
        s = self.sessions.get(name, {})
        self.faraday_url = s.get("faraday_url")
        self.token = s.get("token")
        self.ignore_ssl = bool(s.get("ignore_ssl"))
        self.workspace = s.get("workspace")

    def _fold_active_into_session(self):
        """Persist the live flat values back into the active session entry.

        Lets `workspace select` (which sets the flat workspace) and a fresh login
        update the active session without each caller touching the registry.
        """
        if self.active_session and self.active_session in self.sessions:
            s = self.sessions[self.active_session]
            s["faraday_url"] = self.faraday_url
            s["token"] = self.token
            s["ignore_ssl"] = bool(self.ignore_ssl)
            s["workspace"] = self.workspace

    def add_session(
        self,
        name,
        faraday_url,
        token,
        ignore_ssl=False,
        workspace=None,
        kind="server",
        user=None,
        make_active=True,
    ):
        """Create/replace a named session; make it active by default + save."""
        self.sessions[name] = {
            "faraday_url": faraday_url,
            "token": token,
            "ignore_ssl": bool(ignore_ssl),
            "workspace": workspace,
            "kind": kind,
            "user": user,
        }
        if make_active:
            self.active_session = name
            self._sync_from_session(name)
        self.save()

    def resolve_session(self, ref):
        """Resolve a session by 1-based index (as shown in `auth list`) or name.

        Accepts an int-like index ("1"), an exact session name, or — as a
        convenience — a unique match on the session's user/email. Returns the
        session name, or None when it doesn't resolve (or is an ambiguous
        user match).
        """
        ref = str(ref).strip()
        names = list(self.sessions)
        if ref.isdigit():
            idx = int(ref) - 1
            if 0 <= idx < len(names):
                return names[idx]
            return None
        if ref in self.sessions:
            return ref
        # Fall back to a unique user/email match.
        by_user = [n for n in names if (self.sessions[n].get("user") or "") == ref]
        if len(by_user) == 1:
            return by_user[0]
        return None

    def use_session(self, name) -> bool:
        """Switch the active connection to ``name``. Returns False if unknown."""
        if name not in self.sessions:
            return False
        self.active_session = name
        self._sync_from_session(name)
        self.save()
        return True

    def remove_session(self, name) -> bool:
        """Delete a session. Clears the active connection if it was active."""
        if name not in self.sessions:
            return False
        del self.sessions[name]
        if self.active_session == name:
            self.active_session = None
            self.faraday_url = None
            self.token = None
            self.ignore_ssl = False
            self.workspace = None
        self.save()
        return True

    # -- persistence --------------------------------------------------------

    def load(self):
        try:
            if self.config_exists():
                with open(self.config_file) as f:
                    config_data = yaml.load(f, Loader=yaml.FullLoader)
                # An empty config file parses to None — treat it as "no config".
                if not config_data:
                    return
                self.custom_plugins_path = config_data.get("settings", {}).get("custom_plugins_path")
                self.ignore_info_severity = config_data.get("settings", {}).get("ignore_info_severity", False)
                self.auto_command_detection = config_data.get("settings", {}).get("auto_command_detection", True)

                self.sessions = config_data.get("sessions") or {}
                self.active_session = config_data.get("active_session")

                # Migrate a pre-sessions config: the legacy `auth` block becomes a
                # session named after its host, active by default.
                auth = config_data.get("auth", {}) or {}
                if not self.sessions and auth.get("faraday_url") and auth.get("token"):
                    name = urlparse(auth["faraday_url"]).hostname or "default"
                    self.sessions[name] = {
                        "faraday_url": auth["faraday_url"],
                        "token": auth["token"],
                        "ignore_ssl": bool(auth.get("ignore_ssl")),
                        "workspace": config_data.get("faraday", {}).get("workspace"),
                        "kind": "server",
                    }
                    if not self.active_session:
                        self.active_session = name

                # FaradAI-scan endpoints + registration transients.
                fs = config_data.get("faradai_scan", {}) or {}
                self.faradai_dashboard_url = fs.get("dashboard_url") or DEFAULT_FARADAI_DASHBOARD_URL
                self.faradai_scan_url = fs.get("url") or DEFAULT_FARADAI_SCAN_URL
                self.faradai_pending_email = fs.get("pending_email")
                self.faradai_pending_password = fs.get("pending_password")
                # Migrate a legacy stored SaaS token into a `faradai-scan`
                # session (only when one isn't already registered).
                if fs.get("token") and FARADAI_SCAN_SESSION not in self.sessions:
                    self.sessions[FARADAI_SCAN_SESSION] = {
                        "faraday_url": fs.get("url") or DEFAULT_FARADAI_SCAN_URL,
                        "token": fs["token"],
                        "ignore_ssl": False,
                        "workspace": fs.get("workspace"),
                        "kind": "saas",
                    }

                # Sync the flat active view from the active session.
                if self.active_session and self.active_session in self.sessions:
                    self._sync_from_session(self.active_session)
                else:
                    self.active_session = None
        except KeyError:
            pass

    def save(self):
        # Fold the live flat values back into the active session so a workspace
        # change or fresh login persists without the caller touching the registry.
        self._fold_active_into_session()
        saas = self.sessions.get(FARADAI_SCAN_SESSION, {})
        config_data = {
            # Back-compat mirror of the active connection (older readers + humans).
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
            "sessions": self.sessions,
            "active_session": self.active_session,
            "faradai_scan": {
                "dashboard_url": self.faradai_dashboard_url,
                "url": self.faradai_scan_url,
                # Mirror the SaaS session (for downgrade / raw-file inspection);
                # None when there's no faradai-scan session.
                "token": saas.get("token"),
                "workspace": saas.get("workspace"),
                "pending_email": self.faradai_pending_email,
                "pending_password": self.faradai_pending_password,
            },
        }
        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f)


active_config = Config()
