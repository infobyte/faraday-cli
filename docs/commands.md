# Commands

## help

Using the help command you can get info of any command.
```
$ faraday-cli help -v

Documented commands (use 'help -v' for verbose/'help <topic>' for details):

Agents
--------------------------------------------------------------------------------
get_agent           Get agent
list_agents         List agents
run_executor        Run executor
...
```

```
$  faraday-cli help auth
usage: auth [-h] [-f FARADAY_URL] [-i] [-u USER] [-p PASSWORD]

Authenticate with a faraday server

optional arguments:
  -h, --help            show this help message and exit
  -f FARADAY_URL, --faraday-url FARADAY_URL
                        Faraday server URL
  -i, --ignore-ssl      Ignore SSL verification
  -u USER, --user USER  Faraday user
  -p PASSWORD, --password PASSWORD
                        Faraday password
```

## Authentication

### auth

Authenticate with your faraday server.

*Optional rguments:*

| Syntax      | Description |
|:-----	|------:	|
| -f/--faraday-url FARADAY_URL       | url of your faraday server      |
| -i/--ignore-ssl   | Ignore SSL certificate validation        |
| -i/--ignore-ssl   | Ignore SSL certificate validation        |
| -u/--user USER  | Faraday user       |
| -p/--password PASSWORD  | Faraday password       |

```
$ faraday-cli auth
Faraday url [http://localhost:5985]: http://localhost:5985
User: faraday
Password:
Saving config
✔ Authenticated with faraday: http://localhost:5985
```

### status

Show the status of your current authentication.

```
$ faraday-cli status
FARADAY SERVER         IGNORE SSL    VERSION         VALID TOKEN    WORKSPACE
---------------------  ------------  --------------  -------------  -----------
http://localhost:5985  False         community-3.14  ✔              test
```

## Workspaces

### list_ws

List workspaces created in faraday.

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -j/--json-output      | Show output in json     |
| -p/--pretty   | Show table in a pretty format       |

```
$ faraday-cli list_ws -p
+--------+---------+------------+---------+----------+----------+------------+
| NAME   |   HOSTS |   SERVICES | VULNS   | ACTIVE   | PUBLIC   | READONLY   |
|--------+---------+------------+---------+----------+----------+------------|
| test   |      13 |         13 | 39      | True     | False    | False      |
+--------+---------+------------+---------+----------+----------+------------+
```

### delete_ws

Delete workspace from faraday.

*Required Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| WORKSPACE_NAME      | Workspace name     |

```
$ faraday-cli delete_ws test1
Deleting workspace: test1
Deleted workspace: test1
```

### get_ws

Get details of a workspace.

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -w WORKSPACE_NAME      | Workspace name     |
| -j/--json-output      | Show output in json     |
| -p/--pretty   | Show table in a pretty format       |

```
$ faraday-cli get_ws -p
+--------+----------+----------+------------+---------+------------+---------+
| NAME   | ACTIVE   | PUBLIC   | READONLY   |   HOSTS |   SERVICES |   VULNS |
|--------+----------+----------+------------+---------+------------+---------|
| test   | True     | False    | False      |      13 |         13 |      39 |
+--------+----------+----------+------------+---------+------------+---------+
```

### select_ws

Select your active workspace, unless you use the ```-w``` argument all the commands will use this workspace.

*Required Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| WORKSPACE_NAME      | Workspace name     |

```
$ faraday-cli select_ws test
✔ Selected workspace: test
```

### create_ws

Create a new workspace in faraday.

*Required Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| WORKSPACE_NAME      | Workspace name     |

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -d/--dont-select      | Dont select after create     |

```
$ faraday-cli create_ws test_workspace
✔ Created workspace: test_workspace
```

## Hosts

### list_hosts

List hosts in workspace.

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -w WORKSPACE_NAME     | Workspace name    |
| -p/--pretty   | Show table in a pretty format       |
| -j/--json-output      | Show output in json     |
| -ip/--list-ip   | Show ip only      |
| --port PORT   | Listen in port      |

```
$ faraday-cli list_hosts -p
+------+------------+---------+-------------+------------+---------+
|   ID | IP         | OS      | HOSTNAMES   |   SERVICES |   VULNS |
|------+------------+---------+-------------+------------+---------|
|   11 | 127.0.0.1  | unknown |             |          1 |       3 |
|    3 | 127.0.0.10 | unknown |             |          1 |       3 |
|    6 | 127.0.0.11 | unknown |             |          1 |       3 |
|    5 | 127.0.0.12 | unknown |             |          1 |       3 |
|    7 | 127.0.0.13 | unknown |             |          1 |       3 |
|   13 | 127.0.0.2  | unknown |             |          1 |       3 |
|    2 | 127.0.0.3  | unknown |             |          1 |       3 |
|    9 | 127.0.0.4  | unknown |             |          1 |       3 |
|   10 | 127.0.0.5  | unknown |             |          1 |       3 |
|    4 | 127.0.0.6  | unknown |             |          1 |       3 |
|    8 | 127.0.0.7  | unknown |             |          1 |       3 |
|    1 | 127.0.0.8  | unknown |             |          1 |       3 |
|   12 | 127.0.0.9  | unknown |             |          1 |       3 |
+------+------------+---------+-------------+------------+---------+
```

### get_host

Get host information.

*Requirement Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| host_id     | ID of the host    |

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -w WORKSPACE_NAME     | Workspace name    |
| -p/--pretty   | Show table in a pretty format       |
| -j/--json-output      | Show output in json     |

```
$ faraday-cli get_host 13 -p
Host:
+------+-----------+---------+-------------+---------+---------+---------+
|   ID | IP        | OS      | HOSTNAMES   | OWNER   | OWNED   |   VULNS |
|------+-----------+---------+-------------+---------+---------+---------|
|   13 | 127.0.0.2 | unknown |             | faraday | False   |       3 |
+------+-----------+---------+-------------+---------+---------+---------+

Services:
+------+--------+---------------+------------+--------+-----------+----------+---------+
|   ID | NAME   | DESCRIPTION   | PROTOCOL   |   PORT | VERSION   | STATUS   |   VULNS |
|------+--------+---------------+------------+--------+-----------+----------+---------|
|   13 | ssh    |               | tcp        |     22 | unknown   | open     |       2 |
+------+--------+---------------+------------+--------+-----------+----------+---------+

Vulnerabilities:
+------+------------------------------------------+------------+----------+-------------+---------+
|   ID | NAME                                     | SEVERITY   | STATUS   | CONFIRMED   | TOOL    |
|------+------------------------------------------+------------+----------+-------------+---------|
|   37 | SSH Weak Encryption Algorithms Supported | MED        | opened   | False       | Openvas |
|   38 | SSH Weak MAC Algorithms Supported        | LOW        | opened   | False       | Openvas |
|   39 | TCP timestamps                           | LOW        | opened   | False       | Openvas |
+------+------------------------------------------+------------+----------+-------------+---------+
```

### delete_host

Delete host.

*Requirement Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| host_id     | ID of the host    |

*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -w WORKSPACE_NAME     | Workspace name    |

```
$ faraday-cli delete_host 13
Host deleted
```

### create_hosts

Create hosts.


*Optional Arguments:*

| Syntax      | Description |
|:-----	|------:	|
| -w WORKSPACE_NAME     | Workspace name    |
| -d/--host-data HOST_DATA     | Host data in json format   |
| --stdin     | Read host-data from stdin   |

*host data schema*:
```
{'type': 'array', 'items': {'type': 'object', 'properties':
    {'ip': {'type': 'string'}, 'description': {'type': 'string'},
    'hostnames': {'type': 'array'}}, 'required': ['ip', 'description']}}
```

You can pass the host data via stdin.
```
$ echo '[{"ip": "1.1.1.5", "description": "some text"}]' | faraday-cli create_host --stdin
```

If you pass the data as an argument it needs to be escaped like this (only in command mode, not in shell mode).
```
$ faraday-cli create_host -d \\''[{"ip": "stan.local", "description": "some server"}]'\\'
```
