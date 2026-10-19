# Faraday Cli

Use [Faraday](https://faradaysec.com/) directly from your favorite terminal. faraday-cli is the official client that makes automating your security workflows easier.

<script src="https://asciinema.org/a/384132.js" id="asciicast-384132" async data-autoplay="false" data-size="small"></script>

## Features

- **Two ways to use it** — an interactive shell or single commands for scripts and pipelines
- **Import tool output** — process reports from 100+ security tools ([Faraday Plugins](https://github.com/infobyte/faraday_plugins)), or run a supported tool and upload its results automatically
- **Workspaces, hosts, services and vulnerabilities** — list, create, update and delete them, with stats and a workspaces dashboard
- **AI pentests with FaradAI** — launch FaradAI scans and triage from the terminal, including self-registration on the FaradAI-scan SaaS
- **Agents and scanners** — run local Faraday Agents (runners) and server-side cloud agents (scanners)
- **Several servers** — saved connection sessions to switch between servers or users
- **Executive reports** — generate them from your templates (commercial versions of Faraday)

## Command overview

| Command | What it does |
|---------|--------------|
| `auth`, `status` | Connect to a Faraday server and manage saved sessions |
| `workspace` | List, create, select, enable/disable workspaces and show a dashboard |
| `host`, `service`, `vuln` | Query and manage a workspace's data |
| `tool report`, `tool run` | Import a tool report, or run a tool and import its output |
| `stats` | Vulnerability statistics |
| `pentest`, `triage`, `faradai` | FaradAI scans, triage and FaradAI-scan SaaS registration |
| `scanners` | List and run server-side cloud agents |
| `agent` (`runners`) | List and run local Faraday Agents |
| `executive_report` | Generate executive reports |
| `set`, `help`, `version` | Settings, help and version |

See [Commands](commands.md) for every option.


# Examples

Here you have some snippets of different workflows you can generate using faraday-cli

#### One-line Continuous Scan

Scan the assets of a workspace with nmap and import the results back.

```shell
$ faraday-cli host list -ip -w other_ws | nmap -iL - -oX /tmp/nmap.xml && faraday-cli tool report -w other_ws /tmp/nmap.xml
```

!!! info
    In this case there should be a workspace named "other_ws" with hosts in it.

#### AI pentest with FaradAI

Launch an AI-driven pentest against a target using the FaradAI cloud agent
(scanner) and watch it to completion.

```shell
$ faraday-cli pentest --target https://example.com --watch
```

!!! info
    `pentest` is the shortcut for `faradai scan`. Use `--advanced` for the deeper
    80-round audit, `triage -w <workspace>` to re-test the findings of a
    workspace, or `scanners run <id|name>` to run any cloud agent with its own
    parameters. See [Commands](commands.md#faradai).

#### One-line nmap scan of all the hosts in the workspace

To scan all the hosts inside a workspace with ```nmap``` and import the results back to faraday.

```shell
$ for ip in $(faraday-cli host list -ip); do faraday-cli tool run "nmap -Pn -p443,80 -sV --script=+http-enum -vvv $ip"; done
```

#### Scan your subdomains

Use a tool like ```assetfinder``` to do a domains lookup, scan them with nmap and send the results to faraday

```shell
$ assetfinder -subs-only example.com| sort | uniq |awk 'BEGIN { ORS = ""; print " {\"target\":\""}
{ printf "%s%s", separator, $1, $2
separator = ","}END { print "\"}" }' | faraday-cli agent run -a 1 -e nmap --stdin
```

!!! info
    For this purpose, an agent is created and already connected to run the nmap executor.

#### Send Faraday Executive Reports by mail

Run a daily scan and send your report

```shell
$ faraday-cli executive_report create -t "generic_default.docx (generic) (Word)" --confirmed -d /tmp/report.docx && echo "Faraday Daily Report" | mail -s "Daily Report" user@example.com -A /tmp/report.docx
```

#### Load your assets from your cloud provider

Here you can list your assets using a cli from your provider (in this example Digital Ocean), then generate a json with that information and use faraday-cli to send it to faraday.

```shell
$ doctl compute droplet list --format PublicIPv4,Name --no-header | awk 'BEGIN { ORS = ""; print " ["}
{ printf "%s{\"ip\": \"%s\", \"description\": \"%s\"}", separator, $1, $2
separator = ", "}END { print "] " }' | faraday-cli host create --stdin
```


## Support

- [Documentation](https://docs.faraday-cli.faradaysec.com)
- [Issue tracker](https://github.com/infobyte/faraday-cli/issues)

??? question "Too many secrets?"
    ```
    QW55IGZhbnMgb2YgVGhlIFNuZWFrZXJzPz8gVHJ5IHJ1bm5pbmcgZmFyYWRheS1jbGkgYWZ0ZXIgc2V0dGluZyB0aGlzICJleHBvcnQgS0FLRVJfTU9ERT0xIg
    ```
