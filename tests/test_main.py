"""One-shot dispatch in main(): how the CLI args are turned into a command line."""

import pytest

from faraday_cli.shell import main as main_mod


@pytest.fixture
def dispatched(monkeypatch):
    lines = []

    class _FakeShell:
        def onecmd_plus_hooks(self, line):
            lines.append(line)

    monkeypatch.setattr(main_mod, "FaradayShell", _FakeShell)
    monkeypatch.setattr(main_mod.sys, "exit", lambda code=0: None)
    return lines


def test_single_string_command_is_passed_as_is(dispatched):
    main_mod.main(["workspace list"])
    assert dispatched == ["workspace list"]


def test_separate_args_keep_spaces_quoted(dispatched):
    main_mod.main(["scanners", "run", "--agent", "First Scan"])
    assert dispatched == ["scanners run --agent 'First Scan'"]
