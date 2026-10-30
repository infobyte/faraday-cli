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
    mock.reload_api_client = lambda: None
    fc._CommandSet__cmd_internal = mock
    # Single-active-connection model: scan/triage use fc._cmd.api_client after
    # _ensure_connected. Default the tests to "already connected" so they exercise
    # the run path; the onboarding/SaaS-switch path is covered explicitly.
    fc._ensure_connected = lambda force_saas, target=None: True
    return fc


def test_register_posts_email_and_password(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp(200, {"status": "code_sent"})

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)
    fc = _bound_cmd()
    args = SimpleNamespace(email="me@corp.com", password="hunter2pass", dashboard_url="https://scan.x/_ai")
    fc.register(args)

    assert captured["url"] == "https://scan.x/_ai/api/register"
    assert captured["json"] == {"email": "me@corp.com", "password": "hunter2pass"}
    assert any("Verification code sent" in o for o in fc._cmd.outputs)
    # explicit password → stashed, not announced as generated
    assert faradai_mod.active_config.faradai_pending_email == "me@corp.com"
    assert faradai_mod.active_config.faradai_pending_password == "hunter2pass"
    assert not any("Generated password" in o for o in fc._cmd.outputs)


def test_register_autogenerates_password_when_omitted(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        return _FakeResp(200, {"status": "code_sent"})

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)
    fc = _bound_cmd()
    fc.register(SimpleNamespace(email="me@corp.com", password=None, dashboard_url="https://scan.x/_ai"))

    pw = captured["json"]["password"]
    assert pw and len(pw) >= 12  # a real generated password was sent
    assert any(c in "!@#$%^&*-_=+" for c in pw)  # satisfies the special-char policy
    assert faradai_mod.active_config.faradai_pending_password == pw  # stashed for verify
    assert any("Generated password" in o for o in fc._cmd.outputs)  # shown to the user


def test_register_reports_disabled_on_404(monkeypatch):
    monkeypatch.setattr(faradai_mod.requests, "post", lambda *a, **k: _FakeResp(404))
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)
    fc = _bound_cmd()
    fc.register(SimpleNamespace(email="me@corp.com", password="hunter2pass!", dashboard_url="https://scan.x/_ai"))
    assert any("not enabled" in e for e in fc._cmd.errors)


def test_verify_uses_positional_code_and_pending_creds(monkeypatch):
    """`faradai verify <code>` with no --email/--password uses the pending
    registration stashed by `faradai register`, and clears it on success."""
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent["json"] = json
        return _FakeResp(200, {"token": "tok-9", "faraday_url": "https://scan.real", "workspace": "ext_corp_com"})

    added = {}

    def fake_add_session(name, **kw):
        added["name"] = name
        added["kw"] = kw

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_url", "https://scan.x", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_email", "me@corp.com", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_password", "stashed-pw!", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "add_session", fake_add_session)

    fc = _bound_cmd()
    # positional code, no --email/--password/--code
    fc.verify(
        SimpleNamespace(code="123456", code_flag=None, email=None, password=None, dashboard_url="https://scan.x/_ai")
    )

    # pending creds were used in the POST
    assert sent["json"] == {"email": "me@corp.com", "code": "123456", "password": "stashed-pw!"}
    # a faradai-scan session was created (active) with the returned token + workspace
    assert added["name"] == faradai_mod.FARADAI_SCAN_SESSION
    assert added["kw"]["token"] == "tok-9"
    assert added["kw"]["workspace"] == "ext_corp_com"
    assert added["kw"]["kind"] == "saas"
    assert added["kw"]["make_active"] is True
    # pending cleared before the session was saved
    assert faradai_mod.active_config.faradai_pending_email is None
    assert faradai_mod.active_config.faradai_pending_password is None


def test_verify_errors_without_code(monkeypatch):
    fc = _bound_cmd()
    fc.verify(
        SimpleNamespace(code=None, code_flag=None, email="x@y.com", password="p", dashboard_url="https://scan.x/_ai")
    )
    assert any("Missing code" in e for e in fc._cmd.errors)


def test_scan_posts_to_active_connection(monkeypatch):
    """scan uses the active connection's api_client + its workspace."""
    monkeypatch.setattr(faradai_mod.active_config, "workspace", "ext_corp_com", raising=False)
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
    fc._cmd.api_client = _FakeClient()
    fc.scan(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert posted["agent_id"] == 3
    assert posted["args"]["TARGET"] == "http://app.corp.com"
    assert posted["args"]["ROUNDS"] == 20  # standard default
    assert posted["workspaces"] == ["ext_corp_com"]
    assert any("Command id(s): 11" in o for o in fc._cmd.outputs)


def test_scan_aborts_when_not_connected(monkeypatch):
    """When _ensure_connected returns False (onboarding declined), scan bails."""

    class _FakeClient:
        def run_cloud_agent(self, *a, **k):  # pragma: no cover - must not run
            raise AssertionError("run must not be called when not connected")

        def list_cloud_agents(self):  # pragma: no cover
            raise AssertionError("must not reach agent discovery")

    fc = _bound_cmd()
    fc._ensure_connected = lambda force_saas, target=None: False
    fc._cmd.api_client = _FakeClient()
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction="x",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert not any("launched" in o for o in fc._cmd.outputs)


def test_scan_standalone_warns_deprecated(monkeypatch):
    """--standalone still works but prints a deprecation note (switches to SaaS)."""
    monkeypatch.setattr(faradai_mod.active_config, "workspace", "ext_corp_com", raising=False)
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["workspaces"] = workspaces
            return {"command_ids": [{"id": 11}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert any("deprecated" in o for o in fc._cmd.outputs)
    assert posted["workspaces"] == ["ext_corp_com"]


def test_scan_advanced_uses_80_rounds(monkeypatch):
    monkeypatch.setattr(faradai_mod.active_config, "workspace", "ext_corp_com", raising=False)
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["args"] = args
            return {"command_ids": [{"id": 12}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    # --advanced with no explicit --rounds → 80
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=True,
            goal=None,
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
            target="http://app.corp.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=35,
            advanced=True,
            goal=None,
            watch=False,
        )
    )
    assert posted["args"]["ROUNDS"] == 35


def test_scan_authenticated_autodiscovers_single_workspace(monkeypatch):
    """Authenticated scan with no --workspace + no active workspace uses the
    user's sole accessible workspace (pentester scoped to one)."""
    monkeypatch.setattr(faradai_mod.active_config, "workspace", None, raising=False)
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def get_workspaces(self):
            return [{"name": "ext_onlyone_com", "active": True}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["workspaces"] = workspaces
            return {"command_ids": [{"id": 50}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    fc.scan(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            target="http://app.onlyone.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert posted["workspaces"] == ["ext_onlyone_com"]


def test_scan_authenticated_multiple_workspaces_requires_flag(monkeypatch):
    """When the user can access several workspaces, auto-discovery refuses and
    asks for --workspace instead of guessing."""
    monkeypatch.setattr(faradai_mod.active_config, "workspace", None, raising=False)
    launched = {"called": False}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def get_workspaces(self):
            return [{"name": "ws_a", "active": True}, {"name": "ws_b", "active": True}]

        def run_cloud_agent(self, *a, **k):
            launched["called"] = True
            return {"command_ids": [{"id": 1}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    fc.scan(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction="full",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert launched["called"] is False
    assert any("No workspace resolved" in e for e in fc._cmd.errors)


def test_login_stores_sole_workspace(monkeypatch):
    """faradai login creates + activates a faradai-scan session with the user's
    token and sole ext_<domain> workspace."""
    added = {}

    class _FakeApi:
        def __init__(self, *a, **k):
            pass

        def login(self, email, password):
            return True

        def get_token(self, second_factor=None):
            return "tok-login"

        def get_workspaces(self):
            return [{"name": "ext_mycompany_com", "active": True}]

    monkeypatch.setattr(faradai_mod, "FaradayApi", _FakeApi, raising=False)
    # faradai.login imports FaradayApi locally; patch the source module too.
    import faraday_cli.api_client as _apimod

    monkeypatch.setattr(_apimod, "FaradayApi", _FakeApi, raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_url", "https://scan.real", raising=False)
    monkeypatch.setattr(
        faradai_mod.active_config,
        "add_session",
        lambda name, **kw: added.update(name=name, **kw),
    )
    fc = _bound_cmd()
    fc.login(SimpleNamespace(email="me@mycompany.com", password="pw!", scan_url=None))

    assert added.get("name") == faradai_mod.FARADAI_SCAN_SESSION
    assert added.get("token") == "tok-login"
    assert added.get("workspace") == "ext_mycompany_com"
    assert added.get("kind") == "saas"
    assert added.get("make_active") is True


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
        instruction=None,
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
        instruction=None,
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
        instruction=None,
        dry_run=True,
        watch=False,
    )
    fc.triage(args)

    assert launched["called"] is True  # dry-run proceeds despite empty ws


# --- default instruction from the wizard templates --------------------------


def _scan_capture_client():
    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def get_workspaces(self):
            return [{"name": "ext_corp_com", "active": True}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["args"] = args
            return {"command_ids": [{"id": 1}]}

    return posted, _FakeClient()


def test_scan_default_instruction_standard(monkeypatch):
    from faraday_cli.shell.modules import faradai_instructions as instr

    monkeypatch.setattr(faradai_mod.active_config, "workspace", None, raising=False)
    posted, client = _scan_capture_client()
    fc = _bound_cmd()
    fc._cmd.api_client = client
    fc.scan(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction=None,
            goal=None,
            mode="Dual",
            rounds=None,
            advanced=False,
            watch=False,
        )
    )
    # standard scan → condensed standard instruction + default standard goal
    assert posted["args"]["INSTRUCTION"] == instr.STANDARD_INSTRUCTION
    assert posted["args"]["GOAL"] == instr.STANDARD_GOAL
    # both stay within the server's 256-char cap
    assert len(posted["args"]["INSTRUCTION"]) <= 256
    assert len(posted["args"]["GOAL"]) <= 256


def test_scan_default_instruction_advanced_and_goal(monkeypatch):
    from faraday_cli.shell.modules import faradai_instructions as instr

    monkeypatch.setattr(faradai_mod.active_config, "workspace", None, raising=False)
    posted, client = _scan_capture_client()
    fc = _bound_cmd()
    fc._cmd.api_client = client
    fc.scan(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            target="http://app.corp.com",
            workspace=None,
            instruction=None,
            goal="focus on auth",
            mode="Dual",
            rounds=None,
            advanced=True,
            watch=False,
        )
    )
    # advanced scan → wizard full-audit template; --goal flows to GOAL
    assert posted["args"]["INSTRUCTION"] == instr.ADVANCED_INSTRUCTION
    assert posted["args"]["GOAL"] == "focus on auth"


def test_triage_default_instruction(monkeypatch):
    from faraday_cli.shell.modules import faradai_instructions as instr

    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI Triage", "slug": "faradai-triage"}]

        def get_workspace(self, name):
            return {"stats": {"total_vulns": 5}}

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["args"] = args
            return {"command_ids": [{"id": 9}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    fc.triage(
        SimpleNamespace(
            standalone=False,
            agent_id=None,
            workspace=["ws-a"],
            severities=None,
            confirmed_only=False,
            auto_close_fp=False,
            target_filter=None,
            reproduce=False,
            batch_size=None,
            rounds=None,
            goal=None,
            instruction=None,
            dry_run=False,
            watch=False,
        )
    )
    # triage cloud agent has no INSTRUCTION param — the brief goes in GOAL
    assert posted["args"]["GOAL"] == instr.TRIAGE_INSTRUCTION
    assert "INSTRUCTION" not in posted["args"]
    assert len(posted["args"]["GOAL"]) <= 256


def test_all_default_instructions_within_256():
    """Every default INSTRUCTION/GOAL must fit the server's 256-char cap."""
    from faraday_cli.shell.modules import faradai_instructions as instr

    for name in (
        "STANDARD_INSTRUCTION",
        "ADVANCED_INSTRUCTION",
        "TRIAGE_INSTRUCTION",
        "STANDARD_GOAL",
        "ADVANCED_GOAL",
    ):
        assert len(getattr(instr, name)) <= 256, name


def test_activate_saas_session_self_heals_invalid_token(monkeypatch):
    """A stored faradai-scan session with a dead token must NOT just error:
    _activate_saas_session detects it (is_token_valid False), removes the stale
    session, and re-runs the guided onboarding so the user re-creates the
    account."""
    monkeypatch.setattr(
        faradai_mod.active_config,
        "sessions",
        {faradai_mod.FARADAI_SCAN_SESSION: {"faraday_url": "https://scan.real", "token": "stale", "kind": "saas"}},
        raising=False,
    )

    class _FakeApi:
        def __init__(self, *a, **k):
            pass

        def is_token_valid(self):
            return False

    monkeypatch.setattr(faradai_mod, "FaradayApi", _FakeApi, raising=False)
    import faraday_cli.api_client as _apimod

    monkeypatch.setattr(_apimod, "FaradayApi", _FakeApi, raising=False)

    flow = {"removed": False, "onboarded": False}
    monkeypatch.setattr(
        faradai_mod.active_config,
        "remove_session",
        lambda name: flow.update(removed=True) or True,
    )

    def fake_onboarding(target=None):
        # stale session must already be removed before onboarding runs
        flow["onboarded"] = flow["removed"]
        return True

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_guided_onboarding", fake_onboarding)
    monkeypatch.setattr(faradai_mod, "is_interactive", lambda: True)

    ok = fc._activate_saas_session()
    assert ok is True
    assert flow["removed"] is True  # stale session removed
    assert flow["onboarded"] is True  # re-onboarded after removal
    assert any("set it up again" in o for o in fc._cmd.outputs)


def test_ensure_connected_onboards_when_nothing_configured(monkeypatch):
    """With no active session and no --standalone, scan onboards the first-time
    scan-only user into the SaaS instead of erroring."""
    monkeypatch.setattr(faradai_mod.active_config, "active_session", None, raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "sessions", {}, raising=False)

    flow = {"onboarded": False}

    def fake_onboarding(target=None):
        flow["onboarded"] = True
        return True

    fc = _bound_cmd()
    # Don't stub _ensure_connected here — exercise the real one.
    del fc._ensure_connected
    monkeypatch.setattr(fc, "_guided_onboarding", fake_onboarding)
    monkeypatch.setattr(faradai_mod, "is_interactive", lambda: True)

    ok = fc._ensure_connected(False)  # no --standalone, nothing configured
    assert ok is True
    assert flow["onboarded"] is True


# --- onboarding: email-domain vs target pre-check (fail before the OTP) ------


def test_target_host_parsing():
    from faraday_cli.shell.modules.faradai import _target_host

    assert _target_host("https://faradaysec.com") == "faradaysec.com"
    assert _target_host("https://app.example.com:8443/x") == "app.example.com"
    assert _target_host("example.com") == "example.com"
    assert _target_host("") == ""


def test_email_domain_covers_target():
    from faraday_cli.shell.modules.faradai import _email_domain_covers_target

    # public provider / wrong company → does NOT cover a real target
    assert _email_domain_covers_target("famato@gmail.com", "faradaysec.com") is False
    assert _email_domain_covers_target("me@other.com", "faradaysec.com") is False
    # same domain or a subdomain of it → covered
    assert _email_domain_covers_target("me@faradaysec.com", "faradaysec.com") is True
    assert _email_domain_covers_target("me@faradaysec.com", "app.faradaysec.com") is True
    # unknown target or email → permissive (server is the final judge)
    assert _email_domain_covers_target("me@corp.com", "") is True


def test_onboarding_warns_and_aborts_on_domain_mismatch(monkeypatch):
    """`pentest --target faradaysec.com` with a gmail email must warn and abort
    WITHOUT sending the OTP (no /api/register call) — and never offer to
    "register anyway", even if the user would say yes."""
    posted = []
    monkeypatch.setattr(faradai_mod.requests, "post", lambda *a, **k: posted.append(a) or _FakeResp(200, {}))
    monkeypatch.setattr(faradai_mod.click, "prompt", lambda *a, **k: "famato@gmail.com")
    monkeypatch.setattr(faradai_mod.click, "confirm", lambda *a, **k: True)  # would accept

    fc = _bound_cmd()
    ok = fc._guided_onboarding(target="https://faradaysec.com")
    assert ok is False
    assert posted == []  # OTP never sent
    joined = " ".join(fc._cmd.outputs)
    assert "faradaysec.com" in joined and "gmail.com" in joined


def test_onboarding_matching_domain_proceeds(monkeypatch):
    """A matching email domain skips the warning and proceeds to register."""
    calls = {"register": False, "verify": False}

    def fake_register(email, password, url):
        calls["register"] = True
        return True

    def fake_verify(code, email, password, url):
        calls["verify"] = True
        return True

    confirmed = {"asked": False}
    monkeypatch.setattr(faradai_mod.click, "confirm", lambda *a, **k: confirmed.update(asked=True) or True)
    monkeypatch.setattr(faradai_mod.click, "prompt", lambda *a, **k: "me@faradaysec.com")

    fc = _bound_cmd()
    fc._do_register = fake_register
    fc._do_verify = fake_verify
    ok = fc._guided_onboarding(target="https://faradaysec.com")
    assert ok is True
    assert calls["register"] and calls["verify"]
    assert confirmed["asked"] is False  # no mismatch → never asked to confirm


def test_verify_uses_pending_dashboard_url(monkeypatch):
    """`register --dashboard-url <custom>` then `verify <code>` (no URL) must
    finish on the SAME custom dashboard, not fall back to the default SaaS."""
    urls = []

    def fake_post(url, json=None, timeout=None):
        urls.append(url)
        if url.endswith("/api/register"):
            return _FakeResp(200, {"status": "code_sent"})
        return _FakeResp(200, {"token": "tok-1", "faraday_url": "https://custom.x", "workspace": "ext_corp_com"})

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)
    monkeypatch.setattr(faradai_mod.active_config, "add_session", lambda *a, **k: None)

    fc = _bound_cmd()
    fc.register(SimpleNamespace(email="me@corp.com", password="hunter2pass!", dashboard_url="https://custom.x/_ai"))
    assert faradai_mod.active_config.faradai_pending_dashboard_url == "https://custom.x/_ai"

    fc.verify(SimpleNamespace(code="123456", code_flag=None, email=None, password=None, dashboard_url=None))
    assert urls[-1] == "https://custom.x/_ai/api/verify"  # pending URL won
    # cleared after a successful verify
    assert faradai_mod.active_config.faradai_pending_dashboard_url is None


# --- review fixes (#113) -------------------------------------------------------


def test_activate_saas_session_keeps_session_on_connection_error(monkeypatch):
    """A SaaS that can't be reached is not an expired token: the stored
    faradai-scan session must be kept (no removal, no re-onboarding)."""
    from faraday_cli.api_client.exceptions import RequestError

    monkeypatch.setattr(
        faradai_mod.active_config,
        "sessions",
        {faradai_mod.FARADAI_SCAN_SESSION: {"faraday_url": "https://scan.real", "token": "good", "kind": "saas"}},
        raising=False,
    )

    class _FakeApi:
        def __init__(self, *a, **k):
            pass

        def is_token_valid(self):
            raise RequestError("Connection error")

    import faraday_cli.api_client as _apimod

    monkeypatch.setattr(_apimod, "FaradayApi", _FakeApi, raising=False)
    flow = {"removed": False, "onboarded": False}
    monkeypatch.setattr(faradai_mod.active_config, "remove_session", lambda name: flow.update(removed=True) or True)
    monkeypatch.setattr(faradai_mod.active_config, "use_session", lambda name: True)

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_guided_onboarding", lambda target=None: flow.update(onboarded=True) or True)

    assert fc._activate_saas_session() is True
    assert flow == {"removed": False, "onboarded": False}


def test_is_token_valid_raises_on_connection_error(monkeypatch):
    """is_token_valid() must not report a connection error as an invalid token."""
    from simple_rest_client.exceptions import ClientConnectionError

    api = _api()

    def boom():
        raise ClientConnectionError("refused")

    monkeypatch.setattr(api.faraday_api.login, "validate", boom)
    try:
        api.is_token_valid()
    except Exception as e:
        assert "Connection error" in str(e)
    else:
        raise AssertionError("expected a connection error, got a token verdict")


def test_ensure_connected_points_to_saved_sessions(monkeypatch):
    """Saved server sessions but none active → tell the user to `auth use`,
    don't push them into the public SaaS signup."""
    monkeypatch.setattr(faradai_mod.active_config, "active_session", None, raising=False)
    monkeypatch.setattr(
        faradai_mod.active_config,
        "sessions",
        {"corp": {"faraday_url": "https://corp", "token": "t", "kind": "server"}},
        raising=False,
    )
    fc = _bound_cmd()
    del fc._ensure_connected
    onboarded = []
    monkeypatch.setattr(fc, "_guided_onboarding", lambda target=None: onboarded.append(1) or True)

    assert fc._ensure_connected(False) is False
    assert onboarded == []
    assert any("auth use" in e and "corp" in e for e in fc._cmd.errors)


def test_onboarding_not_started_without_tty(monkeypatch):
    """Nothing configured in a script/CI → clear error, no prompts."""
    monkeypatch.setattr(faradai_mod.active_config, "active_session", None, raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "sessions", {}, raising=False)
    monkeypatch.setattr(faradai_mod, "is_interactive", lambda: False)
    fc = _bound_cmd()
    del fc._ensure_connected
    onboarded = []
    monkeypatch.setattr(fc, "_guided_onboarding", lambda target=None: onboarded.append(1) or True)

    assert fc._ensure_connected(False) is False
    assert onboarded == []
    assert any("faraday-cli auth" in e for e in fc._cmd.errors)


def test_error_message_handles_non_object_json():
    assert FaradaiCommands._error_message(_FakeResp(500, ["boom"])) == "Error (500): ['boom']"
    assert FaradaiCommands._error_message(_FakeResp(400, {"error": "invalid_email"})) == "Error (400): invalid_email"
    assert FaradaiCommands._error_message(_FakeResp(502)) == "Error (502)"


def test_verify_404_clears_pending_credentials(monkeypatch):
    """No (or expired) pending registration server-side → drop the local stash."""
    monkeypatch.setattr(faradai_mod.requests, "post", lambda url, json=None, timeout=None: _FakeResp(404))
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_email", "me@corp.com", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_password", "secret!Pass1", raising=False)

    fc = _bound_cmd()
    fc.verify(SimpleNamespace(code="123456", code_flag=None, email=None, password=None, dashboard_url=None))
    assert faradai_mod.active_config.faradai_pending_email is None
    assert faradai_mod.active_config.faradai_pending_password is None


def test_onboarding_ip_target_does_not_suggest_email_at_ip(monkeypatch):
    fc = _bound_cmd()
    monkeypatch.setattr(faradai_mod.click, "prompt", lambda *a, **k: "user@foo.com")
    monkeypatch.setattr(faradai_mod.click, "confirm", lambda *a, **k: False)
    assert fc._guided_onboarding(target="10.0.0.5") is False
    warning = " ".join(fc._cmd.outputs)
    assert "IP targets" in warning
    assert "email at '10.0.0.5'" not in warning


def test_workspaces_cover_target():
    from faraday_cli.shell.modules.faradai import _workspaces_cover_target

    assert _workspaces_cover_target(["ext_gmail_com"], "faradaysec.com") is False
    assert _workspaces_cover_target(["ext_other_com"], "faradaysec.com") is False
    assert _workspaces_cover_target(["ext_faradaysec_com"], "faradaysec.com") is True
    assert _workspaces_cover_target(["ext_faradaysec_com"], "app.faradaysec.com") is True
    # not a label boundary → no match
    assert _workspaces_cover_target(["ext_faradaysec_com"], "evilfaradaysec.com") is False
    # hyphenated domains survive the lossy slug
    assert _workspaces_cover_target(["ext_my_corp_com"], "api.my-corp.com") is True
    # any covering / operator-managed workspace → allowed (server decides)
    assert _workspaces_cover_target(["ext_gmail_com", "ext_faradaysec_com"], "faradaysec.com") is True
    assert _workspaces_cover_target(["client_acme"], "faradaysec.com") is True
    assert _workspaces_cover_target([], "faradaysec.com") is True


def test_scan_refuses_out_of_scope_target_before_launch(monkeypatch):
    """gmail-registered workspace → faradaysec.com: refused client-side, never launched."""
    monkeypatch.setattr(faradai_mod.active_config, "workspace", "ext_gmail_com", raising=False)
    launched = []

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, *a, **k):
            launched.append(a)
            return {"command_ids": [{"id": 1}]}

    fc = _bound_cmd()
    fc._cmd.api_client = _FakeClient()
    ns = dict(
        standalone=False,
        agent_id=None,
        target="https://faradaysec.com",
        workspace=None,
        instruction="full",
        mode="Dual",
        rounds=None,
        advanced=False,
        goal=None,
        watch=False,
    )
    fc.scan(SimpleNamespace(**ns))
    assert launched == []
    assert any("Out of scope" in e for e in fc._cmd.errors)
    # operator-authorized escape hatch still reaches the server
    fc.scan(SimpleNamespace(**ns, skip_scope_check=True))
    assert len(launched) == 1
