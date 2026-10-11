"""Unit tests for the FaradAI cloud-agent command group.

These are offline unit tests (no live Faraday server): they mock the
simple_rest_client resource methods so the assertions target the CLI's own
logic — the run-body shape (the regression guard against the tkt_70 bug) and
the FaradAI auto-discovery.
"""

from types import SimpleNamespace

from faraday_cli.api_client import FaradayApi
from faraday_cli.shell.modules.faradai import _find_faradai_agent


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
