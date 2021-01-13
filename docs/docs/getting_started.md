## Installation Instructions

!!! info "Python version"
    Python 3.7 and up required.

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

## Using Faraday Cli

Faraday Cli can be used in two ways

* As individual commands
* As a shell

### As commands
Every faraday cli command can be used as an individual command from the command line.

This is useful when integrating faraday cli to batch process, scripts or pipelines.

```
$ faraday-cli list_ws
NAME      HOSTS    SERVICES  VULNS    ACTIVE    PUBLIC    READONLY
------  -------  ----------  -------  --------  --------  ----------
test         13          13  39       True      False     False
```



### As a shell

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
Faraday> list_ws
NAME      HOSTS    SERVICES  VULNS    ACTIVE    PUBLIC    READONLY
------  -------  ----------  -------  --------  --------  ----------
test         13          13  39       True      False     False
```


!!! info "Faraday token expiration"
    You may want to change the faraday token expiration time, so you don't have to authenticate so often.

    The default is 12 hours.

    To do it change de value of ```api_token_expiration```(expressed in seconds) in your faraday ````server.ini````
