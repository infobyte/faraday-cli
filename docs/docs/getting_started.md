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
$ faraday-cli auth

Faraday url [http://localhost:5985]:
User: faraday

Password:
Saving config
✔ Authenticated with faraday: http://localhost:5985
```

## Select an active Workspace

```
$ faraday-cli select workspace test
✔ Selected workspace: test
```

## Now load information into faraday

### Process reports from any of the many tools we support

```
$ faraday-cli process report /path/to/openvas.xml
📄 Processing Openvas report
⬆ Sending data to workspace: test
✔ Done
```


### Or run the tools with the cli

Faraday Cli can be used in two ways to do that

* As individual commands
* As a shell

#### As commands
Every faraday cli command can be used as an individual command from the command line.

This is useful when integrating faraday cli to batch process, scripts or pipelines.

```
$ faraday-cli process tool \"nmap localhost\"
💻 Processing Nmap command
Starting Nmap 7.80 ( https://nmap.org ) at 2021-01-14 13:34 -03
Nmap scan report for localhost (127.0.0.1)
Host is up (0.0010s latency).
Other addresses for localhost (not scanned): ::1
Not shown: 500 closed ports, 490 filtered ports
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http
88/tcp    open  kerberos-sec
443/tcp   open  https
445/tcp   open  microsoft-ds
5432/tcp  open  postgresql
5900/tcp  open  vnc
8000/tcp  open  http-alt
9000/tcp  open  cslistener
49156/tcp open  unknown

Nmap done: 1 IP address (1 host up) scanned in 2.55 seconds
⬆ Sending data to workspace: test
✔ Done
```



#### As a shell

It also can be used as a shell and run any command in the same instance.


```
$ faraday-cli

    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/

Server: http://localhost:5985
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
88/tcp    open  kerberos-sec
443/tcp   open  https
445/tcp   open  microsoft-ds
5432/tcp  open  postgresql
5900/tcp  open  vnc
8000/tcp  open  http-alt
9000/tcp  open  cslistener
49156/tcp open  unknown

Nmap done: 1 IP address (1 host up) scanned in 5.45 seconds
⬆ Sending data to workspace: test
✔ Done
[ws:test]>
```

!!! info
    For more information check out our [commands](../commands/) section.

### Change settings

You can change some settings from the cli itself.

* _custom_plugins_path_ **(Path where the cli will look for custom plugins)**
* _ignore_info_severity_ **(If set to True the cli will ignore all INFORMATIONAL vulnerabilities)** [DEFAULT: False]

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
