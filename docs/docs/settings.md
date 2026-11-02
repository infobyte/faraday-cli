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
| `auto_command_detection` | `True` | If `True`, the cli processes and uploads the output of any supported tool you run (see [Auto-command detection](commands.md#auto-command-detection)) |
| `hostname_resolution` | `False` | If `True`, resolve hostnames when processing tool output |

`custom_plugins_path`, `ignore_info_severity` and `auto_command_detection` are
saved in the configuration file and kept between runs. The rest of the
settings (including `hostname_resolution`) only last for the current session.

The other settings in the list (`allow_style`, `echo`, `editor`, `quiet`,
`timing`…) are the standard ones of the interactive shell library
([cmd2](https://cmd2.readthedocs.io/)).

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

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FARADAY_CLI_CONFIG` | `~/.faraday-cli.yml` | Path of the configuration file |
| `FARADAY_CLI_TIMEOUT` | `10000` | Timeout of each request to the Faraday server, **in seconds** |
| `FARADAY_CLI_EXECUTOR_<EXECUTOR>_<PARAM>` | — | Default value of an executor parameter for `agent run` (e.g. `FARADAY_CLI_EXECUTOR_NMAP_TARGET`); see [agent run](commands.md#agent-run) |

### Example: CI/CD pipeline

In a pipeline there is no one to answer prompts, so pass everything as
arguments or environment variables:

```bash
# keep the pipeline's config apart from yours
export FARADAY_CLI_CONFIG="$CI_PROJECT_DIR/.faraday-cli.yml"

faraday-cli auth -f https://faraday.example.com -u scanner -p "$SCANNER_PASSWORD"
faraday-cli workspace select production-scan

# import a report generated earlier in the pipeline, tagged with the build
faraday-cli tool report scan.xml --vuln-tag "build-$CI_PIPELINE_ID" --min-severity low

# or run an agent executor with its parameters from the environment
export FARADAY_CLI_EXECUTOR_NMAP_TARGET=10.0.0.0/24
faraday-cli agent run -a 1 -e nmap
```
