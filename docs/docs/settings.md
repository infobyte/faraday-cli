# Settings

## Global settings

You can list or change some settings from the cli itself with `set`.

```
$ faraday-cli set
Name                    Value                           Description
--------------------------------------------------------------------------------------------------------------------
allow_style             Terminal                        Allow ANSI text style sequences in output (valid values:
                                                        Always, Never, Terminal)
always_show_hint        False                           Display tab completion hint even when completion suggestions
                                                        print
auto_command_detection  True                            Enable/disable automatic command detection
custom_plugins_path     None                            Path of custom plugins folder
echo                    False                           Echo command issued into output
editor                  vi                              Program used by 'edit'
feedback_to_output      False                           Include nonessentials in '|', '>' results
hostname_resolution     False                           Resolve hostname
ignore_info_severity    False                           Ignore Informational vulnerabilities from reports and
                                                        commands
max_completion_items    50                              Maximum number of CompletionItems to display during tab
                                                        completion
quiet                   False                           Don't print nonessential feedback
scripts_add_to_history  True                            Scripts and pyscripts add commands to history
timing                  False                           Report execution times

$ faraday-cli set ignore_info_severity true
ignore_info_severity - was: False
now: True
```

The faraday-cli specific settings are:

| Setting | Default | Description |
|---------|---------|-------------|
| `custom_plugins_path` | `None` | Path where the cli will look for custom [Faraday Plugins](https://github.com/infobyte/faraday_plugins) |
| `ignore_info_severity` | `False` | If `True`, informational vulnerabilities are ignored in reports and commands |
| `auto_command_detection` | `True` | If `True`, in shell mode the cli tries to process any supported tool you run (see [Shell Mode](getting_started.md#shell-mode)) |
| `hostname_resolution` | `False` | If `True`, resolve hostnames when processing tool output |

`custom_plugins_path`, `ignore_info_severity` and `auto_command_detection` are
saved in the configuration file and kept between runs. The rest of the
settings (including `hostname_resolution`) only last for the current session.

## Configuration file

faraday-cli stores its configuration in `~/.faraday-cli.yml`. Use the
`FARADAY_CLI_CONFIG` environment variable to point it to another file (handy to
keep separate configurations or to test without touching yours):

```
$ FARADAY_CLI_CONFIG=~/faraday-cli-lab.yml faraday-cli auth
```

The file contains:

* **`sessions`** — every saved connection (server URL, token, SSL setting,
  active workspace, user), and **`active_session`**, the one in use. Manage them
  with [`auth list`/`auth use`/`auth rm`](commands.md#auth-list).
* **`auth`** / **`faraday`** — a copy of the active connection and workspace,
  kept for compatibility with older versions.
* **`settings`** — the saved settings described above.
* **`faradai_scan`** — the FaradAI-scan SaaS endpoints and, while a
  registration is pending, its email and password (removed once
  `faradai verify` succeeds).

A configuration file from an older version (a single `auth` block) is migrated
automatically to a session named after the server host.

!!! warning
    The file holds API tokens (and, during a SaaS registration, a password), so
    faraday-cli writes it readable by your user only (`0600`). Don't share it or
    commit it to a repository.
