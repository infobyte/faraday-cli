## Install

```shell script
git clone git@gitlab.com:faradaysec/faraday-cli.git
cd faraday-cli
pip install .
```

> Install autocomplete
>
>add ". /path/to/faraday-cli-autocomplete_zsh.sh" to .zshrc file
>
>add ". /path/to/faraday-cli-autocomplete_bash.sh" to .bashrc file



## Commands

> Login

Configure login for farday-cli

```shell script
faraday-cli login
```

> View faraday-cli status

```shell script
faraday-cli status
Faraday Cli - Status

faraday_url            session                                                ssl_verify
---------------------  -----------------------------------------------------  ------------
http://localhost:5985  XXXXXXXXX                                              False


workspace
-----------
demo
```

> Select default workspace

```shell script
faraday-cli workspace -a select -n WORKSPACE_NAME
```

> List workspaces

```shell script
faraday-cli workspace
```

> Create a workspaces

```shell script
faraday-cli workspace -a create -n WORKSPACE_NAME
```

> Create a workspaces

```shell script
faraday-cli workspace -a create -n WORKSPACE_NAME
```

> Delete a workspaces

```shell script
faraday-cli workspace -a delete -n WORKSPACE_NAME
```

> Import vulns from tool report

```shell script
faraday-cli report "/path/to/report.xml"
```

> Import vulns from command

```shell script
faraday-cli command "ping -c 1 www.google.com"
```