# Faraday on the terminal
Use faraday directly from your favorite terminal


## Install from source
```shell script
git clone https://github.com/infobyte/faraday-cli.git
cd faraday-cli
pip install .
```


## Install from pip

```
pip install faraday-cli
```

## Use it like a command

### Get help
Get help of any command

```shell script
$ faraday-cli help create_ws
usage: create_ws [-h] [-d] workspace_name

Create Workspace

positional arguments:
  workspace_name     Workspace name

optional arguments:
  -h, --help         show this help message and exit
  -d, --dont-select  Dont select after create
```


### Login

Configure auth for farday-cli

```shell script
$ faraday-cli auth
```
![Example](./docs/docs/images/auth.svg)

### View faraday-cli status

```shell script
$ faraday-cli status
FARADAY SERVER         IGNORE SSL    VERSION    VALID TOKEN    WORKSPACE
---------------------  ------------  ---------  -------------  -----------
http://localhost:5985  False         corp-3.12  ✔
```


### Create a workspace
When you create a workspace by default is selected as active, unless you use the "-d" flag
```shell script
$ faraday-cli create_ws some_name
✔ Created workspace: some_name
```

### Select active workspace

```shell script
$ faraday-cli select_ws some_name
✔ Selected workspace: some_name
```

### List workspaces

```shell script
$ faraday-cli list_ws
NAME         HOSTS    SERVICES    VULNS  ACTIVE    PUBLIC    READONLY
---------  -------  ----------  -------  --------  --------  ----------
some_name       14          13       39  True      False     False
```

### Delete a workspace

```shell script
$ faraday-cli delete_ws some_name
```

### List hosts of a workspace

```shell script
$ faraday-cli list_host
  ID  IP           OS       HOSTNAMES          SERVICES  VULNS
----  -----------  -------  ---------------  ----------  -------
 574  127.0.0.1    unknown                            1  3
 566  127.0.0.10   unknown                            1  3
 569  127.0.0.11   unknown                            1  3
 568  127.0.0.12   unknown                            1  3
 570  127.0.0.13   unknown                            1  3
 576  127.0.0.2    unknown                            1  3
 565  127.0.0.3    unknown                            1  3
 572  127.0.0.4    unknown                            1  3
 573  127.0.0.5    unknown                            1  3
 567  127.0.0.6    unknown                            1  3
 571  127.0.0.7    unknown                            1  3
 564  127.0.0.8    unknown                            1  3
 575  127.0.0.9    unknown                            1  3
 590  58.76.184.4  unknown  www.googlec.com           0  -
```

### Get host

```shell script
$ faraday-cli get_host 574

$ faraday-cli get_host 574
Host:
  ID  IP         OS       HOSTNAMES    OWNER    OWNED      VULNS
----  ---------  -------  -----------  -------  -------  -------
 574  127.0.0.1  unknown               faraday  False          3

Services:
  ID  NAME    DESCRIPTION    PROTOCOL      PORT  VERSION    STATUS      VULNS
----  ------  -------------  ----------  ------  ---------  --------  -------
2638  ssh                    tcp             22  unknown    open            2

Vulnerabilities:
   ID  NAME                                      SEVERITY    STATUS    CONFIRMED    TOOL
-----  ----------------------------------------  ----------  --------  -----------  -------
13509  SSH Weak Encryption Algorithms Supported  MED         opened    False        Openvas
13510  SSH Weak MAC Algorithms Supported         LOW         opened    False        Openvas
13511  TCP timestamps                            LOW         opened    False        Openvas
```

### Create hosts

```shell script
$ faraday-cli create_host -d \''[{"ip": "stan.local", "description": "some server"}]'\'
```

Or pipe it
```shell script
$ echo '[{"ip": "1.1.1.5", "description": "some text"}]' | faraday-cli create_host --stdin

```
**The escaping of the single quotes (\\') is only needed when using it as a command.
In the shell or using pipes it not necessary**

### Delete host

```shell script
$ faraday-cli delete_host HOST_ID
```

### Import vulnerabilities from tool report

```shell script
$ faraday-cli process_report "/path/to/report.xml"
```
![Example](./docs/docs/images/process_report.svg)

### Import vulnerabilities from command

```shell script
$ faraday-cli ping -c 1 www.google.com
```
![Example](./docs/docs/images/command.svg)

### List agents

```shell script
$ faraday-cli list_agent
  id  name      active    status    executors
----  --------  --------  --------  -----------
   8  internal  True      online    nmap
```

### Get agent executors

```shell script
$ faraday-cli get_agent 8
  id  name      active    status
----  --------  --------  --------
   8  internal  True      online
Executors:
  id  name    parameters
----  ------  -------------------------------------------------------------------------------------------
   9  nmap    target, option_pn, option_sc, option_sv, port_list, top_ports, host_timeout, script_timeout
```

### Run executor

```shell script
$ faraday-cli run_executor -a 1 -e nmap -p \''{"target": "www.google.com"}'\'
Run executor: internal/nmap [{'successful': True}]
```

### Different output

Most of the commands support different ways to show output
* In json (-j)
* In a pretty table (-p)

```shell script
$ faraday-cli list_ws
NAME         HOSTS    SERVICES    VULNS  ACTIVE    PUBLIC    READONLY
---------  -------  ----------  -------  --------  --------  ----------
some_name       14          13       39  True      False     False

$ faraday-cli list_ws -p
+-----------+---------+------------+---------+----------+----------+------------+
| NAME      |   HOSTS |   SERVICES |   VULNS | ACTIVE   | PUBLIC   | READONLY   |
|-----------+---------+------------+---------+----------+----------+------------|
| some_name |      14 |         13 |      39 | True     | False    | False      |
+-----------+---------+------------+---------+----------+----------+------------+


$ faraday-cli list_ws -j
[
    {
        "update_date": "2020-12-04T18:46:46.473892+00:00",
        "name": "some_name",
        "scope": [],
        "_id": 116,
        "id": 116,
        "public": false,
        "readonly": false,
        "active_agents_count": 0,
        "duration": {
            "start_date": null,
            "end_date": null
        },
        "stats": {
            "code_vulns": 0,
            "critical_vulns": 0,
            "unclassified_vulns": 0,
            "hosts": 14,
            "medium_vulns": 13,
            "high_vulns": 0,
            "web_vulns": 0,
            "low_vulns": 26,
            "info_vulns": 0,
            "total_vulns": 39,
            "services": 13,
            "std_vulns": 39
        },
        "create_date": "2020-12-04T18:46:46.453040+00:00",
        "description": "",
        "active": true,
        "customer": ""
    }
]

```


### Specify workspace

The commands use by default the active workspace, but you can specify other with the "-w" parameter


### Continuous scan your assets with faraday

For example run nmap for all the hosts in faraday that listen on the 443 port and import the results back to faraday
```shell
$ faraday-cli list_host --port 443 -ip | nmap -iL - -oX /tmp/nmap.xml  && faraday-cli process_report /tmp/nmap.xml
```

## Use it like a shell

Faraday-cli can be used as a shell and have all the same commands you have as a cli

![Example](./docs/docs/images/shell.svg)


## With Faraday commercial version

If you have a Faraday commercial version you can automate report generation and download

You can filter vulnerabilities
* --ignore-info (ignore info/unclassified vulnerabilities)
* --severity (only include vulnerabilities with the selected severities)
* --confirmed (only include confirmed vulnerabilities)

```shell
$ faraday-cli generate_executive_report -t \'"generic_default.docx (generic)"\'  --title title --summary summary --enterprise company  -o /tmp/test.docx  --ignore-info
Report generated: /tmp/test.docx
```
