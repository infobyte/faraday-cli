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

    monkeypatch.setattr(faradai_mod.requests, "post", fake_post)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_url", "https://scan.x", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", None, raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_email", "me@corp.com", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_pending_password", "stashed-pw!", raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "save", lambda: None)

    fc = _bound_cmd()
    # positional code, no --email/--password/--code
    fc.verify(
        SimpleNamespace(code="123456", code_flag=None, email=None, password=None, dashboard_url="https://scan.x/_ai")
    )

    # pending creds were used in the POST
    assert sent["json"] == {"email": "me@corp.com", "code": "123456", "password": "stashed-pw!"}
    # token + workspace stored, pending cleared
    assert faradai_mod.active_config.faradai_scan_token == "tok-9"
    assert faradai_mod.active_config.faradai_scan_workspace == "ext_corp_com"
    assert faradai_mod.active_config.faradai_pending_email is None
    assert faradai_mod.active_config.faradai_pending_password is None


def test_verify_errors_without_code(monkeypatch):
    fc = _bound_cmd()
    fc.verify(
        SimpleNamespace(code=None, code_flag=None, email="x@y.com", password="p", dashboard_url="https://scan.x/_ai")
    )
    assert any("Missing code" in e for e in fc._cmd.errors)


def test_scan_standalone_without_token_triggers_onboarding(monkeypatch):
    """A first-time `scan --standalone` (no stored token) runs the guided
    register→verify onboarding, then proceeds to scan with the new token."""
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", None, raising=False)
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_workspace", "ext_corp_com", raising=False)

    flow = {"onboarded": False}

    def fake_onboarding():
        flow["onboarded"] = True
        # emulate a successful onboarding: a token is now present
        faradai_mod.active_config.faradai_scan_token = "tok-new"
        return True

    posted = {}

    class _FakeClient:
        def list_cloud_agents(self):
            return [{"id": 3, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            posted["workspaces"] = workspaces
            return {"command_ids": [{"id": 77}]}

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_guided_onboarding", fake_onboarding)
    monkeypatch.setattr(fc, "_standalone_client", lambda: _FakeClient())
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://t",
            workspace=None,
            instruction="x",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert flow["onboarded"] is True
    assert posted["workspaces"] == ["ext_corp_com"]
    assert any("Command id(s): 77" in o for o in fc._cmd.outputs)


def test_scan_standalone_aborts_if_onboarding_declined(monkeypatch):
    """If onboarding fails/aborts, the scan does not proceed."""
    monkeypatch.setattr(faradai_mod.active_config, "faradai_scan_token", None, raising=False)
    launched = {"called": False}

    class _FakeClient:
        def run_cloud_agent(self, *a, **k):
            launched["called"] = True
            return {}

    fc = _bound_cmd()
    monkeypatch.setattr(fc, "_guided_onboarding", lambda: False)
    monkeypatch.setattr(fc, "_standalone_client", lambda: _FakeClient())
    fc.scan(
        SimpleNamespace(
            standalone=True,
            agent_id=None,
            target="http://t",
            workspace=None,
            instruction="x",
            mode="Dual",
            rounds=None,
            advanced=False,
            goal=None,
            watch=False,
        )
    )
    assert launched["called"] is False


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
        goal=None,
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
            target="http://t",
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
            target="http://t",
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
            target="http://t",
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
    """faradai login persists the user's sole workspace as the scan default."""
    saved = {}

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
        "save",
        lambda: saved.update(
            token=faradai_mod.active_config.faradai_scan_token,
            workspace=faradai_mod.active_config.faradai_scan_workspace,
        ),
    )
    fc = _bound_cmd()
    fc.login(SimpleNamespace(email="me@mycompany.com", password="pw!", scan_url=None))

    assert saved.get("token") == "tok-login"
    assert saved.get("workspace") == "ext_mycompany_com"


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
            target="http://t",
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
            target="http://t",
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
