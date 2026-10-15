"""Unit tests for the generic `scanners` (cloud-agent) command group.

Offline unit tests: they mock the API client so the assertions target the CLI's
own logic — the id-or-name agent resolution, the --param KEY=VALUE parsing, and
the generic run body (shared launch helper) that any cloud agent goes through.
"""

from types import SimpleNamespace

from faraday_cli.shell.modules.cloud_agent_common import resolve_cloud_agent
from faraday_cli.shell.modules.scanner import ScannerCommands, _parse_params


class _FakeCmd:
    """Minimal stand-in for the cmd2 app."""

    def __init__(self, agents=None):
        self.api_client = SimpleNamespace(
            list_cloud_agents=lambda: (agents or []),
        )
        self.errors = []
        self.outputs = []

    def perror(self, msg):
        self.errors.append(msg)

    def poutput(self, msg):
        self.outputs.append(msg)


# --- resolve_cloud_agent (id or name/slug) ----------------------------------


def test_resolve_by_numeric_id_present():
    cmd = _FakeCmd([{"id": 2, "name": "FaradAI", "slug": "faradai"}])
    assert resolve_cloud_agent(cmd, cmd.api_client, "2") == 2
    assert cmd.errors == []


def test_resolve_by_numeric_id_absent_still_returns_id():
    # A numeric id not in the list is passed through so the server 404s (we
    # don't second-guess the operator's explicit id).
    cmd = _FakeCmd([{"id": 2, "name": "FaradAI", "slug": "faradai"}])
    assert resolve_cloud_agent(cmd, cmd.api_client, "99") == 99


def test_resolve_by_name_substring():
    cmd = _FakeCmd(
        [
            {"id": 2, "name": "FaradAI", "slug": "faradai"},
            {"id": 4, "name": "Nessus", "slug": "nessus"},
        ]
    )
    assert resolve_cloud_agent(cmd, cmd.api_client, "nessus") == 4
    assert resolve_cloud_agent(cmd, cmd.api_client, "FARAD") == 2


def test_resolve_zero_match_errors():
    cmd = _FakeCmd([{"id": 2, "name": "FaradAI", "slug": "faradai"}])
    assert resolve_cloud_agent(cmd, cmd.api_client, "zap") is None
    assert any("No cloud agent matching" in e for e in cmd.errors)


def test_resolve_ambiguous_match_errors():
    cmd = _FakeCmd(
        [
            {"id": 2, "name": "FaradAI", "slug": "faradai"},
            {"id": 3, "name": "FaradAI Triage", "slug": "faradai-triage"},
        ]
    )
    assert resolve_cloud_agent(cmd, cmd.api_client, "faradai") is None
    assert any("matches multiple" in e for e in cmd.errors)


# --- _parse_params ----------------------------------------------------------


def test_parse_params_coerces_types():
    out = _parse_params(["TARGET=https://x", "ROUNDS=20", "REPRODUCE=true", "DRY=false"])
    assert out == {
        "TARGET": "https://x",
        "ROUNDS": 20,
        "REPRODUCE": True,
        "DRY": False,
    }


def test_parse_params_preserves_equals_in_value():
    out = _parse_params(["GOAL=a=b=c"])
    assert out == {"GOAL": "a=b=c"}


def test_parse_params_rejects_missing_equals():
    try:
        _parse_params(["JUSTAKEY"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "KEY=VALUE" in str(e)


def test_parse_params_rejects_empty_key():
    try:
        _parse_params(["=value"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "empty key" in str(e)


# --- scanners run (generic body shape) --------------------------------------


def _bound_scanner(api_client):
    fc = ScannerCommands()
    mock = SimpleNamespace(errors=[], outputs=[], api_client=api_client)
    mock.perror = lambda m: mock.errors.append(m)
    mock.poutput = lambda m: mock.outputs.append(m)
    fc._CommandSet__cmd_internal = mock
    return fc


def test_run_scanner_posts_flat_body(monkeypatch):
    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["agent_id"] = agent_id
            captured["args"] = args
            captured["workspaces"] = workspaces
            return {"command_ids": [{"id": 11}]}

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="faradai",
        workspace=["ws1"],
        param=["TARGET=https://x", "ROUNDS=20"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)

    assert captured["agent_id"] == 2
    assert captured["workspaces"] == ["ws1"]
    assert captured["args"] == {"TARGET": "https://x", "ROUNDS": 20}
    assert fc._cmd.errors == []


def test_run_scanner_params_json_takes_precedence():
    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["args"] = args
            return {"command_ids": [{"id": 1}]}

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="2",
        workspace=["ws1"],
        param=["IGNORED=1"],
        params_json='{"TARGET": "https://y", "MODE": "Dual"}',
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert captured["args"] == {"TARGET": "https://y", "MODE": "Dual"}


def test_run_scanner_unknown_agent_aborts():
    class _Client:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI", "slug": "faradai"}]

        def run_cloud_agent(self, *a, **k):  # pragma: no cover - must not run
            raise AssertionError("run must not be called when agent unresolved")

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="doesnotexist",
        workspace=["ws1"],
        param=[],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert any("No cloud agent matching" in e for e in fc._cmd.errors)


# --- --watch polling ---------------------------------------------------------


def test_watch_commands_detects_completion(monkeypatch):
    """watch_commands polls get_workspace_commands and stops when the command
    gets a duration/end_date (finished)."""
    import faraday_cli.shell.modules.cloud_agent_common as cac

    monkeypatch.setattr(cac.time, "sleep", lambda *_: None)  # no real waiting

    calls = {"n": 0}

    class _Client:
        def get_workspace_commands(self, ws):
            calls["n"] += 1
            # first poll: still running (no duration); second: finished.
            if calls["n"] < 2:
                return [{"_id": 42, "duration": "In progress"}]
            return [{"_id": 42, "duration": 12.3, "end_date": "2026-01-01T00:00:00"}]

    cmd = _FakeCmd()
    cac.watch_commands(cmd, _Client(), "my_ws", [42])
    assert any("command 42 finished" in o for o in cmd.outputs)
    assert any("Run finished" in o for o in cmd.outputs)


def test_watch_commands_no_getter_falls_back(monkeypatch):
    """Without a command getter, watch prints the UI hint instead of polling."""
    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:  # no get_workspace_commands / get_commands
        pass

    cmd = _FakeCmd()
    cac.watch_commands(cmd, _Client(), "my_ws", [42])
    assert any("no command-status endpoint" in o for o in cmd.outputs)


# --- interactive param wizard + one-liner -----------------------------------


def test_param_specs_only_executor_args():
    """First Scan shape: `params` holds the executor input schema (just target,
    mandatory), `parameters_data` holds agent CONFIG (workspaces, flags, tags).
    Only the `params` keys are real run args — config-only fields like
    resolve_hostname must NOT be prompted/sent (the server rejects them), and
    workspace is excluded (it goes top-level)."""
    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {
                "id": 1,
                "params": {"target": {"base": "string", "type": "url", "mandatory": True}},
                "parameters_data": {
                    "workspaces": ["suc-firstscan"],
                    "ignore_info": False,
                    "resolve_hostname": False,
                    "vuln_tag": [],
                },
            }

    specs = cac._agent_param_specs(_Client(), 1)
    by = {s["name"]: s for s in specs}
    # ONLY the executor input schema is returned.
    assert list(by) == ["target"]
    assert by["target"]["mandatory"] is True
    assert by["target"]["description"] == "url"
    assert by["target"]["default"] is None  # `base` is a type placeholder
    # config-only fields are NOT run args.
    assert "resolve_hostname" not in by and "ignore_info" not in by
    # workspace is never an arg.
    assert "workspaces" not in by


def test_agent_default_workspaces():
    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {"id": 1, "parameters_data": {"workspaces": ["suc-firstscan", "other"]}}

    assert cac.agent_default_workspaces(_Client(), 1) == ["suc-firstscan", "other"]


def test_param_specs_real_default_beats_placeholder():
    """When parameters_data carries a real value for a schema param, that value
    is the default (not the `base` type placeholder)."""
    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {
                "id": 2,
                "params": {
                    "TARGET": {"base": "string", "mandatory": True},
                    "ROUNDS": {"base": "integer", "mandatory": False},
                },
                "parameters_data": {"ROUNDS": 20, "TARGET": ""},
            }

    by = {s["name"]: s for s in cac._agent_param_specs(_Client(), 2)}
    assert by["ROUNDS"]["default"] == 20
    assert by["TARGET"]["default"] is None


def test_param_specs_flat_params_list():
    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {"id": 2, "params": ["TARGET", "MODE"]}

    specs = cac._agent_param_specs(_Client(), 2)
    assert [s["name"] for s in specs] == ["TARGET", "MODE"]
    assert all(s["mandatory"] is False for s in specs)


def test_build_run_oneliner_quotes_values():
    import faraday_cli.shell.modules.cloud_agent_common as cac

    line = cac.build_run_oneliner("faradai", ["ext_foo_com"], {"TARGET": "https://x y", "ROUNDS": 20})
    assert line.startswith("faraday-cli scanners run --agent faradai")
    assert "-w ext_foo_com" in line
    assert "--param 'TARGET=https://x y'" in line
    assert "--param ROUNDS=20" in line


def test_wizard_prompts_and_runs(monkeypatch):
    """--wizard collects the UNION of schema params + configured values and
    launches with them. Pins the reported bug: the mandatory `target` from the
    `params` input schema is prompted (not just `parameters_data` fields)."""
    import faraday_cli.shell.modules.cloud_agent_common as cac

    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 2, "name": "FaradAI", "slug": "faradai"}]

        def get_cloud_agent(self, aid):
            return {
                "id": 2,
                "params": {
                    "TARGET": {"base": "string", "type": "url", "mandatory": True},
                    "ROUNDS": {"base": "integer", "mandatory": False},
                },
                "parameters_data": {"ROUNDS": 20},
            }

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["args"] = args
            captured["workspaces"] = workspaces
            return {"command_ids": [{"id": 7}]}

    # Type a TARGET (schema-mandatory, no default) and accept the ROUNDS default.
    answers = iter(["https://dvwa.local", ""])
    monkeypatch.setattr(cac.click, "prompt", lambda *a, **k: next(answers))

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="faradai",
        agent_pos=None,
        workspace=["ext_foo_com"],
        param=[],
        params_json=None,
        watch=False,
        wizard=True,
    )
    fc.run_scanner(args)

    assert captured["args"] == {"TARGET": "https://dvwa.local", "ROUNDS": 20}
    # The reproducible one-liner is printed after launch.
    assert any("Reproduce this run with" in o for o in fc._cmd.outputs)
    assert any("--param" in o and "TARGET=https://dvwa.local" in o for o in fc._cmd.outputs)


# --- simplification: positional agent + workspace reconciliation -------------


def test_run_scanner_positional_agent(monkeypatch):
    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 1, "name": "First Scan", "slug": "first-scan"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["agent_id"] = agent_id
            captured["workspaces"] = workspaces
            return {"command_ids": [{"id": 5}]}

    fc = _bound_scanner(_Client())
    # agent given positionally (no -a), workspace from --workspace
    args = SimpleNamespace(
        agent=None,
        agent_pos="first-scan",
        workspace=["WebApp"],
        param=["ignore_info=true"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert captured["agent_id"] == 1
    assert captured["workspaces"] == ["WebApp"]


def test_workspace_derived_from_param_no_dash_w(monkeypatch):
    """The First Scan dead-end: wizard/param filled `workspaces` but no -w and
    no active workspace — the body workspace must come from that param."""
    import faraday_cli.config as cfg

    monkeypatch.setattr(cfg.active_config, "workspace", None, raising=False)
    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 1, "name": "First Scan", "slug": "first-scan"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["workspaces"] = workspaces
            captured["args"] = args
            return {"command_ids": [{"id": 5}]}

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent=None,
        agent_pos="first-scan",
        workspace=None,
        param=["workspaces=WebApp"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    # Workspace comes from the --param workspaces value for the top-level list,
    # and is popped OUT of args (the server rejects it as an executor arg).
    assert captured["workspaces"] == ["WebApp"]
    assert "workspaces" not in captured["args"]
    assert fc._cmd.errors == []


def test_workspace_param_never_lands_in_args(monkeypatch):
    """--param workspaces=… resolves the top-level workspace but must be popped
    out of args so the executor never sees a workspace argument."""
    import faraday_cli.config as cfg

    monkeypatch.setattr(cfg.active_config, "workspace", None, raising=False)
    captured = {}

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 1, "name": "First Scan", "slug": "first-scan"}]

        def run_cloud_agent(self, agent_id, args, workspaces):
            captured["args"] = args
            captured["workspaces"] = workspaces
            return {"command_ids": [{"id": 5}]}

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="first-scan",
        agent_pos=None,
        workspace=["WebApp"],
        param=["target=x.com", "workspaces=ignored"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert captured["workspaces"] == ["WebApp"]  # -w wins
    assert captured["args"] == {"target": "x.com"}  # workspaces popped out


def test_run_scanner_no_agent_errors():
    fc = _bound_scanner(_FakeCmd().api_client)
    args = SimpleNamespace(
        agent=None,
        agent_pos=None,
        workspace=["ws1"],
        param=[],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert any("Which scanner" in e for e in fc._cmd.errors)


# --- client-side executor-arg validation (fail fast, clear message) ----------


def test_unknown_run_args_against_schema():
    """Keys outside the executor `params` schema are unknown; workspace keys
    and schema keys are not. Config-only fields (parameters_data) ARE unknown —
    they're set on the agent, not per run."""

    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {
                "id": 1,
                "params": {"target": {"base": "string", "type": "url", "mandatory": True}},
                "parameters_data": {"resolve_hostname": False, "ignore_info": False},
            }

    assert cac.unknown_run_args(_Client(), 1, {"target": "x.com"}) == []
    assert cac.unknown_run_args(_Client(), 1, {"target": "x.com", "workspaces": "ws"}) == []
    assert cac.unknown_run_args(_Client(), 1, {"target": "x.com", "ignore_info": False, "resolve_hostname": False}) == [
        "ignore_info",
        "resolve_hostname",
    ]


def test_unknown_run_args_no_schema_is_permissive():
    """No `params` schema → the CLI can't validate; the server is the judge."""

    import faraday_cli.shell.modules.cloud_agent_common as cac

    class _Client:
        def get_cloud_agent(self, aid):
            return {"id": 1, "parameters_data": {"ignore_info": False}}

    assert cac.unknown_run_args(_Client(), 1, {"anything": 1}) == []


def test_run_scanner_rejects_config_fields_before_launch(monkeypatch):
    """`--param resolve_hostname=…` must fail fast client-side — naming every
    bad key and the accepted ones — and never reach run_cloud_agent (the
    server would reject the run naming only the first bad key)."""
    import faraday_cli.config as cfg

    monkeypatch.setattr(cfg.active_config, "workspace", None, raising=False)
    launched = []

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 1, "name": "First Scan", "slug": "first-scan"}]

        def get_cloud_agent(self, aid):
            return {
                "id": 1,
                "params": {"target": {"base": "string", "type": "url", "mandatory": True}},
                "parameters_data": {"resolve_hostname": False, "ignore_info": False},
            }

        def run_cloud_agent(self, agent_id, args, workspaces):
            launched.append(args)
            return {"command_ids": [{"id": 5}]}

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="first-scan",
        agent_pos=None,
        workspace=["WebApp"],
        param=["target=x.com", "ignore_info=False", "resolve_hostname=False"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert launched == []  # fail fast: nothing hit the server
    err = "\n".join(fc._cmd.errors)
    assert "ignore_info" in err and "resolve_hostname" in err
    assert "target" in err  # the accepted keys are named


def test_run_scanner_no_oneliner_on_launch_failure(monkeypatch):
    """A failed launch must not print the 'Reproduce this run' one-liner —
    re-running the same failing command is not a reproduction recipe."""
    import faraday_cli.config as cfg

    monkeypatch.setattr(cfg.active_config, "workspace", None, raising=False)

    class _Client:
        def list_cloud_agents(self):
            return [{"id": 1, "name": "First Scan", "slug": "first-scan"}]

        def get_cloud_agent(self, aid):
            return {
                "id": 1,
                "params": {"target": {"base": "string", "type": "url", "mandatory": True}},
            }

        def run_cloud_agent(self, agent_id, args, workspaces):
            raise RuntimeError("boom")

    fc = _bound_scanner(_Client())
    args = SimpleNamespace(
        agent="first-scan",
        agent_pos=None,
        workspace=["WebApp"],
        param=["target=x.com"],
        params_json=None,
        watch=False,
        wizard=False,
    )
    fc.run_scanner(args)
    assert fc._cmd.errors  # the launch error surfaced
    assert not any("Reproduce" in o for o in fc._cmd.outputs)
