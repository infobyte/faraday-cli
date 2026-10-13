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
