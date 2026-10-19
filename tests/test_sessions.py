"""Named connection sessions in Config: add/use/remove + legacy migration."""

import importlib
import os

import pytest


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "faraday-cli.yml"
    monkeypatch.setenv("FARADAY_CLI_CONFIG", str(path))
    import faraday_cli.config as config_mod

    importlib.reload(config_mod)
    return config_mod


def test_add_session_makes_active_and_syncs_flat(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c", workspace="ws1", kind="server")
    assert c.active_session == "corp"
    assert c.faraday_url == "https://corp"
    assert c.token == "tok-c"
    assert c.workspace == "ws1"


def test_roundtrip_persists_sessions(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c", workspace="ws1", kind="server")
    c.add_session("saas", "https://scan", "tok-s", workspace="ext_x", kind="saas")
    c2 = cfg.Config()
    assert set(c2.sessions) == {"corp", "saas"}
    assert c2.active_session == "saas"  # last added is active
    assert c2.faraday_url == "https://scan"
    assert c2.workspace == "ext_x"


def test_use_session_switches_active(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c", workspace="ws1")
    c.add_session("saas", "https://scan", "tok-s", workspace="ext_x", kind="saas")
    assert c.use_session("corp") is True
    assert c.active_session == "corp"
    assert c.faraday_url == "https://corp"
    assert c.workspace == "ws1"
    assert c.use_session("nope") is False


def test_remove_active_session_clears_connection(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c")
    assert c.remove_session("corp") is True
    assert c.active_session is None
    assert c.faraday_url is None
    assert c.token is None
    assert c.remove_session("corp") is False


def test_workspace_change_persists_into_active_session(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c")
    # workspace select sets the flat workspace then saves.
    c.workspace = "picked_ws"
    c.save()
    c2 = cfg.Config()
    assert c2.sessions["corp"]["workspace"] == "picked_ws"
    assert c2.workspace == "picked_ws"


def test_migrates_legacy_auth_block(cfg, tmp_path):
    # Write a pre-sessions config (auth + faraday only).
    path = os.environ["FARADAY_CLI_CONFIG"]
    with open(path, "w") as f:
        f.write(
            "auth:\n"
            "  faraday_url: https://legacy.faraday\n"
            "  token: legacy-tok\n"
            "  ignore_ssl: false\n"
            "faraday:\n"
            "  workspace: legacy_ws\n"
        )
    c = cfg.Config()
    # Legacy connection becomes a session named after the host, active.
    assert "legacy.faraday" in c.sessions
    assert c.active_session == "legacy.faraday"
    assert c.faraday_url == "https://legacy.faraday"
    assert c.workspace == "legacy_ws"


def test_migrates_legacy_faradai_scan_token(cfg):
    path = os.environ["FARADAY_CLI_CONFIG"]
    with open(path, "w") as f:
        f.write(
            "auth:\n"
            "  faraday_url: https://corp\n"
            "  token: corp-tok\n"
            "faradai_scan:\n"
            "  url: https://scan.apps\n"
            "  token: saas-tok\n"
            "  workspace: ext_corp_com\n"
        )
    c = cfg.Config()
    assert cfg.FARADAI_SCAN_SESSION in c.sessions
    saas = c.sessions[cfg.FARADAI_SCAN_SESSION]
    assert saas["token"] == "saas-tok"
    assert saas["workspace"] == "ext_corp_com"
    assert saas["kind"] == "saas"
    # The legacy auth connection is the active one (migration doesn't steal it).
    assert c.active_session == "corp"


def test_two_users_same_server_dont_collide(cfg):
    c = cfg.Config()
    c.add_session("alice@corp", "https://corp", "tok-a", user="alice", workspace="ws_a")
    c.add_session("bob@corp", "https://corp", "tok-b", user="bob", workspace="ws_b")
    # Same server URL, two distinct sessions kept side by side.
    assert set(c.sessions) == {"alice@corp", "bob@corp"}
    c.use_session("alice@corp")
    assert c.token == "tok-a" and c.workspace == "ws_a"
    assert c.sessions["alice@corp"]["user"] == "alice"
    c.use_session("bob@corp")
    assert c.token == "tok-b" and c.workspace == "ws_b"
    assert c.sessions["bob@corp"]["user"] == "bob"


def test_resolve_session_by_index_name_and_user(cfg):
    c = cfg.Config()
    c.add_session("alice@corp", "https://corp", "tok-a", user="alice")
    c.add_session("bob@corp", "https://corp", "tok-b", user="bob")
    # 1-based index (order of insertion)
    assert c.resolve_session("1") == "alice@corp"
    assert c.resolve_session("2") == "bob@corp"
    assert c.resolve_session("3") is None  # out of range
    # exact name
    assert c.resolve_session("bob@corp") == "bob@corp"
    # unique user match
    assert c.resolve_session("alice") == "alice@corp"
    # unknown
    assert c.resolve_session("nobody") is None


def test_resolve_session_ambiguous_user_is_none(cfg):
    c = cfg.Config()
    c.add_session("a1", "https://x", "t1", user="same")
    c.add_session("a2", "https://y", "t2", user="same")
    # two sessions share the same user → ambiguous, must not guess
    assert c.resolve_session("same") is None
    # but the exact names still work
    assert c.resolve_session("a2") == "a2"


def test_legacy_url_without_token_is_kept(cfg):
    path = os.environ["FARADAY_CLI_CONFIG"]
    with open(path, "w") as f:
        f.write("auth:\n  faraday_url: https://notoken.faraday\n  token: null\n  ignore_ssl: true\n")
    c = cfg.Config()
    assert c.active_session is None
    assert c.faraday_url == "https://notoken.faraday"
    assert c.ignore_ssl is True


def test_config_file_is_owner_only(cfg):
    c = cfg.Config()
    c.add_session("corp", "https://corp", "tok-c")
    assert os.stat(os.environ["FARADAY_CLI_CONFIG"]).st_mode & 0o777 == 0o600
