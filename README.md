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

name      hosts    services    vulns
------  -------  ----------  -------
demo         13          19       55
```

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
  id  name            ip              os       hostnames      services    vulns
----  --------------  --------------  -------  -----------  ----------  -------
 188  127.0.0.10      127.0.0.10      unknown                        1        3
 191  127.0.0.11      127.0.0.11      unknown                        1        3
 190  127.0.0.12      127.0.0.12      unknown                        1        3
 192  127.0.0.13      127.0.0.13      unknown                        1        3
```

> Get host of a workspaces

```shell script
#> faraday-cli host -a get -id HOST_ID
  id  name            ip              os       hostnames    owner    owned
----  --------------  --------------  -------  -----------  -------  -------
 199  192.168.0.108  192.168.0.108  unknown    mymac.local   faraday  False


  id  name          description    protocol      port  version                   status      vulns
----  ------------  -------------  ----------  ------  ------------------------  --------  -------
 196  ssh           ssh            tcp             22  OpenSSH 7.8               open            1
 197  http          http           tcp             80  nginx 1.17.10             open            2
 198  kerberos-sec  kerberos-sec   tcp             88  Heimdal Kerberos          open            0
 199  https         https          tcp            443  nginx 1.17.10             open            6
 200  microsoft-ds  microsoft-ds   tcp            445                            open            0
 201  vnc           vnc            tcp           5900  Apple remote desktop vnc  open            6
 202  cslistener    cslistener     tcp           9000                            open            1
```

> Delete host

```shell script
#> faraday-cli host -a delete -id HOST_ID
```