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
#> faraday-cli login
```
![Example](./docs/login.svg)

> View faraday-cli status

```shell script
#> faraday-cli status
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
#> faraday-cli workspace -a select -n WORKSPACE_NAME
```

> Import vulns from tool report

```shell script
#> faraday-cli report "/path/to/report.xml"
```

> Import vulns from command

```shell script
#> faraday-cli command "ping -c 1 www.google.com"
```

> List workspaces

```shell script
#> faraday-cli workspace
```
![Example](./docs/list_workspace.svg)

> Create a workspace

```shell script
#> faraday-cli workspace -a create -n WORKSPACE_NAME
```

> Delete a workspace

```shell script
#> faraday-cli workspace -a delete -n WORKSPACE_NAME
```

> List hosts of a workspace

```shell script
#> faraday-cli host
```
![Example](./docs/list_hosts.svg)

> Get host

```shell script
#> faraday-cli host -a get -id HOST_ID
```
![Example](./docs/get_host.svg)

> Delete host

```shell script
#> faraday-cli host -a delete -id HOST_ID
```