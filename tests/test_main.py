"""One-shot dispatch in main(): how the CLI args are turned into a command line."""

import shlex

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


# --- legacy escaped quoting (#115) ---------------------------------------------
# argv below is exactly what the OS shell hands over for the documented forms
# (checked with `python3 -c "import sys; print(sys.argv[1:])" <args>`); the
# assertion is on the tokens cmd2 will parse back out of the reassembled line.


def _tokens(dispatched):
    assert len(dispatched) == 1
    return shlex.split(dispatched[0])


def test_legacy_escaped_double_quotes_span_several_tokens(dispatched):
    # faraday-cli tool run \"nmap -sn 127.0.0.1\"
    main_mod.main(["tool", "run", '"nmap', "-sn", '127.0.0.1"'])
    assert _tokens(dispatched) == ["tool", "run", "nmap -sn 127.0.0.1"]


def test_legacy_escaped_single_quotes_json(dispatched):
    # faraday-cli host create -d \''[{"ip": "10.0.0.1", "description": "x"}]'\'
    main_mod.main(["host", "create", "-d", '\'[{"ip": "10.0.0.1", "description": "x"}]\''])
    assert _tokens(dispatched) == ["host", "create", "-d", '[{"ip": "10.0.0.1", "description": "x"}]']


def test_legacy_escaped_template_name(dispatched):
    # faraday-cli executive_report create -t \'"generic_default.html (generic) (PDF)"\' --title t
    main_mod.main(["executive_report", "create", "-t", "'generic_default.html (generic) (PDF)'", "--title", "t"])
    template = "generic_default.html (generic) (PDF)"
    assert _tokens(dispatched) == ["executive_report", "create", "-t", template, "--title", "t"]


def test_natural_quoting_is_unchanged(dispatched):
    # faraday-cli tool run "nmap -sn 127.0.0.1" / host create -d '[...]'
    main_mod.main(["tool", "run", "nmap -sn 127.0.0.1"])
    main_mod.main(["host", "create", "-d", '[{"ip": "10.0.0.1", "description": "x"}]'])
    assert shlex.split(dispatched[0]) == ["tool", "run", "nmap -sn 127.0.0.1"]
    assert shlex.split(dispatched[1]) == ["host", "create", "-d", '[{"ip": "10.0.0.1", "description": "x"}]']


def test_quotes_inside_a_value_are_kept(dispatched):
    # quotes that don't wrap the whole token (JSON, KEY="x", it's) stay as they are
    main_mod.main(["scanners", "run", "faradai", "--param", 'GOAL="x"', "--param", "INSTRUCTION=it's"])
    assert _tokens(dispatched) == ["scanners", "run", "faradai", "--param", 'GOAL="x"', "--param", "INSTRUCTION=it's"]


def test_unclosed_leading_quote_is_left_alone(dispatched):
    main_mod.main(["vuln", "update", "1", "--desc", '"never closed', "--name", "n"])
    assert _tokens(dispatched) == ["vuln", "update", "1", "--desc", '"never closed', "--name", "n"]
