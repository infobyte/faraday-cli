"""API severity names must map to their colors, not the default white."""

from cmd2 import Fg as COLORS

from faraday_cli.shell.utils import get_severity_color


def test_medium_severity_is_yellow():
    assert get_severity_color("medium") == COLORS.YELLOW


def test_informational_severity_is_blue():
    assert get_severity_color("informational") == COLORS.BLUE


def test_known_short_names_keep_their_colors():
    assert get_severity_color("critical") == COLORS.MAGENTA
    assert get_severity_color("high") == COLORS.RED
    assert get_severity_color("low") == COLORS.GREEN
