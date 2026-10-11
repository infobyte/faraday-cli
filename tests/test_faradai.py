"""Unit tests for the FaradAI cloud-agent command group.

These are offline unit tests (no live Faraday server): they mock the
simple_rest_client resource methods so the assertions target the CLI's own
logic — the run-body shape (the regression guard against the tkt_70 bug), the
FaradAI auto-discovery, and the SaaS register/verify/standalone flow.
"""

from types import SimpleNamespace

from faraday_cli.api_client import FaradayApi
from faraday_cli.shell.modules import faradai as faradai_mod
from faraday_cli.shell.modules.faradai import FaradaiCommands, _find_faradai_agent


def _api():
    # token must be set or @handle_errors raises MissingConfig before the call.
    return FaradayApi(url="http://faraday.local", token="tok-test")


def test_run_cloud_agent_posts_flat_body():
    """run_cloud_agent must POST exactly {"workspaces", "args"} — NOT the
    legacy executor_data/workspaces_names shape (the tkt_70 regression)."""
    api = _api()
    captured = {}

    def fake_run(cloud_agent_id, body=None):
        captured["id"] = cloud_agent_id
        captured["body"] = body
        return SimpleNamespace(body={"command_ids": [{"id": 7}]})

    api.faraday_api.cloud_agent.run = fake_run

    args = {"TARGET": "http://t", "INSTRUCTION": "x", "MODE": "Dual", "ROUNDS": 40}
    result = api.run_cloud_agent(42, args, ["ws1"])

    assert captured["id"] == 42
    assert captured["body"] == {"workspaces": ["ws1"], "args": args}
    assert set(captured["body"].keys()) == {"workspaces", "args"}
    assert "executor_data" not in captured["body"]
    assert "workspaces_names" not in captured["body"]
    assert result == {"command_ids": [{"id": 7}]}


def test_list_cloud_agents_returns_body():
    api = _api()
    api.faraday_api.cloud_agent.list = lambda: SimpleNamespace(body=[{"id": 1, "name": "FaradAI", "slug": "faradai"}])
    assert api.list_cloud_agents() == [{"id": 1, "name": "FaradAI", "slug": "faradai"}]


class _FakeCmd:
    """Minimal stand-in for the cmd2 app used by _find_faradai_agent."""

    def __init__(self, agents):
        self.api_client = SimpleNamespace(list_cloud_agents=lambda: agents)
        self.errors = []
        self.outputs = []

    def perror(self, msg):
        self.errors.append(msg)

    def poutput(self, msg):
        self.outputs.append(msg)


def test_find_faradai_agent_single_match():
    cmd = _FakeCmd(
        [
            {"id": 5, "name": "FaradAI Scanner", "slug": "faradai"},
            {"id": 6, "name": "Nessus", "slug": "nessus"},
        ]
    )
    agent = _find_faradai_agent(cmd)
    assert agent["id"] == 5
    assert cmd.errors == []


def test_find_faradai_agent_zero_match():
    cmd = _FakeCmd([{"id": 6, "name": "Nessus", "slug": "nessus"}])
    assert _find_faradai_agent(cmd) is None
    assert any("No FaradAI cloud agent" in e for e in cmd.errors)


def test_find_faradai_agent_multiple_match():
    cmd = _FakeCmd(
        [
            {"id": 5, "name": "FaradAI one", "slug": "faradai-1"},
            {"id": 8, "name": "FaradAI two", "slug": "faradai-2"},
        ]
    )
    assert _find_faradai_agent(cmd) is None
    assert any("Multiple FaradAI" in e for e in cmd.errors)


def test_find_faradai_agent_matches_on_slug_only():
    cmd = _FakeCmd([{"id": 9, "name": "Scanner", "slug": "faradai-prod"}])
    agent = _find_faradai_agent(cmd)
    assert agent["id"] == 9


# --- SaaS register / verify / standalone ------------------------------------


class _FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.content = b"x" if payload is not None else b""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _bound_cmd():
    """A FaradaiCommands instance with a mock _cmd (as cmd2 wires at register).

    cmd2's ``_cmd`` is a read-only property backed by the name-mangled
    ``_CommandSet__cmd_internal`` attribute, so set that directly.
    """
    fc = FaradaiCommands()
    mock = SimpleNamespace(errors=[], outputs=[], api_client=None)
    mock.perror = lambda m: mock.errors.append(m)
    mock.poutput = lambda m: mock.outputs.append(m)
    fc._CommandSet__cmd_internal = mock
    return fc


def test_register_posts_email_and_password(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp(200, {"status": "code_sent"})

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    fc = _bound_cmd()
    args = SimpleNamespace(email="me@corp.com", password="hunter2pass", dashboard_url="https://scan.x/_ai")
    fc.register(args)

    assert captured["url"] == "https://scan.x/_ai/api/register"
    assert captured["json"] == {"email": "me@corp.com", "password": "hunter2pass"}
    assert any("Verification code sent" in o for o in fc._cmd.outputs)


def test_register_reports_disabled_on_404(monkeypatch):
    monkeypatch.setattr(faradai_mod.requests, "post", lambda *a, **k: _FakeResp(404))
    fc = _bound_cmd()
    fc.register(SimpleNamespace(email="me@corp.com", password="hunter2pass", dashboard_url="https://scan.x/_ai"))
    assert any("not enabled" in e for e in fc._cmd.errors)


def test_verify_persists_token_to_config(monkeypatch):
    monkeypatch.setattr(
        faradai_mod.requests,
        "post",
        lambda *a, **k: _FakeResp(200, {"token": "tok-9", "faraday_url": "https://scan.real", "email": "me@corp.com"}),
    )
    saved = {}
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_url", "https://scan.x", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", None, raising=False)
    monkeypatch.setattr(
        faradai_mod.active_config,
        "save",
        lambda: saved.update(
            url=faradai_mod.active_config.faradai_scan_url,
            token=faradai_mod.active_config.faradai_scan_token,
        ),
    )
    fc = _bound_cmd()
    fc.verify(
        SimpleNamespace(email="me@corp.com", code="123456", password="hunter2pass", dashboard_url="https://scan.x/_ai")
    )

    assert saved == {"url": "https://scan.real", "token": "tok-9"}


def test_scan_standalone_without_token_errors(monkeypatch):
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", None, raising=False)
    fc = _bound_cmd()
    args = SimpleNamespace(
        standalone=True,
        agent_id=None,
        target="http://t",
        workspace=None,
        instruction="x",
        mode="Dual",
        rounds=None,
        advanced=False,
        watch=False,
    )
    fc.scan(args)
    assert any("Not registered" in e for e in fc._cmd.errors)


def test_scan_standalone_with_token_posts_to_saas(monkeypatch):
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", "tok-9", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_url", "https://scan.real", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_workspace", "ext_corp_com", raising=False)

    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["agent_id"] = agent_id
            posted["args"] = args
            posted["workspaces"] = workspaces
            return {"command_ids": [{"id": 11}]}

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_standalone_client", lambda: _FakeClient())
    args = SimpleNamespace(
        standalone=True,
        agent_id=None,
        target="http://t",
        workspace=None,
        instruction="full",
        mode="Dual",
        rounds=None,
        advanced=False,
        watch=False,
    )
    fc.scan(args)

    assert posted["agent_id"] == 3
    assert posted["args"]["TARGET"] == "http://t"
    assert posted["args"]["ROUNDS"] == 20  # standard default
    assert posted["workspaces"] == ["ext_corp_com"]  # stored ext_<domain> workspace
    assert any("Command id(s): 11" in o for o in fc._cmd.outputs)


def test_scan_advanced_uses_80_rounds(monkeypatch):
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", "tok-9", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_workspace", "ext_corp_com", raising=False)
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["args"] = args
            return {"command_ids": [{"id": 12}]}

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_standalone_client", lambda: _FakeClient())
    # --advanced with no explicit --rounds → 80
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://t",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=True,
            watch=False,
        )
    )
    assert posted["args"]["ROUNDS"] == 80

    # explicit --rounds overrides --advanced
    posted.clear()
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://t",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=35,
            advanced=True,
            watch=False,
        )
    )
    assert posted["args"]["ROUNDS"] == 35


# --- triage -----------------------------------------------------------------


def test_find_faradai_agent_pentest_vs_triage_disambiguation():
    """Both agents contain 'faradai'; pentest lookup must skip the triage one
    and vice-versa (otherwise scan would see 'multiple matches')."""
    agents = [
        {"id": 1, "name": "FaradAI", "slug": "faradai"},
        {"id": 2, "name": "FaradAI Triage", "slug": "faradai-triage"},
    ]
    pentest = _find_faradai_agent(_FakeCmd(agents), kind="pentest")
    triage = _find_faradai_agent(_FakeCmd(agents), kind="triage")
    assert pentest["id"] == 1
    assert triage["id"] == 2


def test_triage_builds_params_and_targets_triage_agent(monkeypatch):
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [
                {"id": 1, "name": "FaradAI", "slug": "faradai"},
                {"id": 2, "name": "FaradAI Triage", "slug": "faradai-triage"},
            ]

        def get_workspace(self, name):
            return {"stats": {"total_vulns": 7}}  # non-empty → triage proceeds

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["agent_id"] = agent_id
            posted["args"] = args
            posted["workspaces"] = workspaces
            return {"command_ids": [{"id": 22}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    args = SimpleNamespace(
        standalone=False,
        agent_id=None,
        workspace=["ws-a", "ws-b"],
        severities="critical,high",
        confirmed_only=True,
        auto_close_fp=False,
        target_filter=None,
        reproduce=True,
        batch_size=10,
        rounds=None,
        goal=None,
        dry_run=False,
        watch=False,
    )
    fc.triage(args)

    assert posted["agent_id"] == 2  # the triage cloud agent, not pentest
    assert posted["args"]["WORKSPACES"] == "ws-a,ws-b"  # mandatory, comma-joined
    assert posted["args"]["SEVERITIES"] == "critical,high"
    assert posted["args"]["CONFIRMED_ONLY"] is True
    assert posted["args"]["REPRODUCE"] is True
    assert posted["args"]["BATCH_SIZE"] == 10
    assert "AUTO_CLOSE_FP" not in posted["args"]  # flag off → omitted
    assert "TARGET" not in posted["args"]  # triage has no TARGET
    assert any("Command id(s): 22" in o for o in fc._cmd.outputs)


def test_triage_refuses_empty_workspace(monkeypatch):
    """A workspace with 0 findings has nothing to triage → refuse pre-flight."""
    launched = {"called": False}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI Triage", "slug": "faradai-triage"}]

        def get_workspace(self, name):
            return {"stats": {"total_vulns": 0}}  # empty

        def run_cloud_agent(self, *a, **k):
            launched["called"] = True
            return {"command_ids": [{"id": 99}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    args = SimpleNamespace(
        standalone=False,
        agent_id=None,
        workspace=["ext_empty_com"],
        severities=None,
        confirmed_only=False,
        auto_close_fp=False,
        target_filter=None,
        reproduce=False,
        batch_size=None,
        rounds=None,
        goal=None,
        dry_run=False,
        watch=False,
    )
    fc.triage(args)

    assert launched["called"] is False  # never dispatched
    assert any("Nothing to triage" in e for e in fc._cmd.errors)


def test_triage_empty_workspace_allowed_with_dry_run(monkeypatch):
    """--dry-run plans even on an empty workspace (skips the pre-flight)."""
    launched = {"called": False}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI Triage", "slug": "faradai-triage"}]

        def get_workspace(self, name):
            return {"stats": {"total_vulns": 0}}

        def run_cloud_agent(self, *a, **k):
            launched["called"] = True
            return {"command_ids": [{"id": 99}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    args = SimpleNamespace(
        standalone=False,
        agent_id=None,
        workspace=["ext_empty_com"],
        severities=None,
        confirmed_only=False,
        auto_close_fp=False,
        target_filter=None,
        reproduce=False,
        batch_size=None,
        rounds=None,
        goal=None,
        dry_run=True,
        watch=False,
    )
    fc.triage(args)

    assert launched["called"] is True  # dry-run proceeds despite empty ws
