## Installation Instructions


### Install
=== "pip"
    ```shell
    $ pip install faraday-cli
    ```

=== "git"
    ```shell
    $ git clone https://github.com/infobyte/faraday-cli.git
    $ cd faraday-cli
    $ pip install .
    ```

!!! info "Python version"
    Python 3.7 and up required.

# Using Faraday Cli

## Authenticate with your Faraday server

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

v:2.1.0
Server: http://localhost:5985
Faraday> auth

Faraday url [http://localhost:5985]:

User: faraday

Password:
Saving config
✔ Authenticated with faraday: http://localhost:5985
Faraday>
```

## Create a workspace or select active Workspace

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

v:2.1.0
Server: http://localhost:5985
Faraday> workspace create test
✔ Created workspace: test
[ws:test]>
```

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

v:2.1.0
Server: http://localhost:5985
Faraday> workspace select test
✔ Selected workspace: test
[ws:test]>
```

## Now load information into faraday

### Process reports from any of the many tools we support

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

v:2.1.0
Server: http://localhost:5985
[ws:test]> tool report /path/to/openvas.xml
📄 Processing Openvas report
⬆ Sending data to workspace: test
✔ Done
```


### Or run the tools with faraday-cli

Faraday Cli can be used in two modes:

* shell mode: faraday-cli reacts as a shell to your commands
* command mode: faraday-cli reacts as a command with parameters

## Shell Mode

In this mode Faraday-cli will react as a shell, so if you type an OS command it will process it as a shell.

If _auto_command_detection_ is enabled it will try to process any tool we support to send the info to faraday.

Or you can use the command ```tool run XXXX```

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

v:2.1.0
Server: http://localhost:5985
[ws:test]> cd /tmp
[ws:test]> ls -l
total 24
drwxr-xr-x@  4 user    wheel  128 Dec  9 09:38 com.google.Keystone
-rw-------   1 root    wheel   36 Dec  9 08:31 fseventsd-uuid
drwxr-xr-x  21 root    wheel  672 Dec  9 08:38 msu-target-6bZPmxQ0
srwxrwxrwx   1 user    wheel    0 Dec  9 08:31 mysql.sock
-rw-------   1 user    wheel    4 Dec  9 08:31 mysql.sock.lock
srwxrwxrwx   1 user    wheel    0 Dec  9 08:31 mysqlx.sock
-rw-------   1 user    wheel    5 Dec  9 08:31 mysqlx.sock.lock
drwxr-xr-x   2 root    wheel   64 Dec  9 08:31 powerlog
drwx------   2 root    wheel   64 Dec  9 08:31 pritunl
[ws:test]> nmap localhost
💻 Processing Nmap command
Starting Nmap 7.80 ( https://nmap.org ) at 2021-01-14 13:34 -03
Nmap scan report for localhost (127.0.0.1)
Host is up (0.00026s latency).
Other addresses for localhost (not scanned): ::1
Not shown: 961 closed ports, 29 filtered ports
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http

Nmap done: 1 IP address (1 host up) scanned in 5.45 seconds
⬆ Sending data to workspace: test
✔ Done
[ws:test]> tool run "nmap localhost"
💻 Processing Nmap command
Starting Nmap 7.80 ( https://nmap.org ) at 2021-01-14 13:34 -03
Nmap scan report for localhost (127.0.0.1)
Host is up (0.00026s latency).
Other addresses for localhost (not scanned): ::1
Not shown: 961 closed ports, 29 filtered ports
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http

Nmap done: 1 IP address (1 host up) scanned in 5.45 seconds
⬆ Sending data to workspace: test
✔ Done
```

You can mix faraday-cli commands with other commands

```
[ws:test]> vuln list | tail -3
   3  Exposed metrics              LOW         opened    False        192.241.149.70 [Service - (443/tcp) https]   grafana.faradaysec.com
   6  name                         CRITICAL    opened    True         123.230.222.247 [Host - ID:3]                sandbox.faradaysec.com
   5  Python Django Admin Panel 2  CRITICAL    opened    False        133.230.222.247 [Service - (443/tcp) https]  sandbox.faradaysec.com
```

```
[ws:test]> vuln list -j| jq '.[0]| {target: .value.target, cve: .value.cve[0], name: .value.name}'
{
  "target": "111.248.115.223",
  "cve": "CVE-2007-0994",
  "name": "Grafana panel detect"
}
```
## Command Mode
Every faraday cli command can be used as an individual command from the command line.

This is useful when integrating faraday cli to batch process, scripts or pipelines.

```
$ faraday-cli tool run \"nmap localhost\"
💻 Processing Nmap command
Starting Nmap 7.80 ( https://nmap.org ) at 2021-01-14 13:34 -03
Nmap scan report for localhost (127.0.0.1)
Host is up (0.0010s latency).
Other addresses for localhost (not scanned): ::1
Not shown: 500 closed ports, 490 filtered ports
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http

Nmap done: 1 IP address (1 host up) scanned in 2.55 seconds
⬆ Sending data to workspace: test
✔ Done
```

!!! info
    For more information check out our [commands](../commands/) section.

### Change settings

You can change some settings from the cli itself.

* _custom_plugins_path_ **(Path where the cli will look for custom plugins)**
* _ignore_info_severity_ **(If set to True the cli will ignore all INFORMATIONAL vulnerabilities)** [DEFAULT: False]
* _auto_command_detection_ **(If set to True the cli will try process a tool when is run in shell mode)** [DEFAULT: True]

```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

Server: http://localhost:5985
[ws:test]> set ignore_info_severity true
ignore_info_severity - was: False
now: True
[ws:test]>
```
