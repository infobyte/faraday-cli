import io
import os
import queue
import argparse
import sys
from urllib.parse import urlparse
from pathlib import Path
import shlex
import getpass
import subprocess


from cmd2 import (
    Cmd,
    style,
    with_argparser,
    Statement,
    Settable,
    with_default_category,
)
import click
from faraday_plugins.plugins.manager import (
    PluginsManager,
    ReportAnalyzer,
    CommandAnalyzer,
)
from simple_rest_client.exceptions import ClientConnectionError
from tabulate import tabulate

from simple_rest_client.exceptions import ClientError

from faraday_cli.extras.halo.halo import Halo
from faraday_cli.config import active_config
from faraday_cli.shell import utils

from faraday_cli.api_client import FaradayApi
from faraday_cli.api_client.exceptions import InvalidCredentials, Invalid2FA
from faraday_cli.shell import modules  # noqa: F401

logo = """
    ______                     __               _________
   / ____/___ __________ _____/ /___ ___  __   / ____/ (_)
  / /_  / __ `/ ___/ __ `/ __  / __ `/ / / /  / /   / / /
 / __/ / /_/ / /  / /_/ / /_/ / /_/ / /_/ /  / /___/ / /
/_/    \__,_/_/   \__,_/\__,_/\__,_/\__, /   \____/_/_/
                                   /____/
"""  # noqa: W605


@with_default_category("Core")
class FaradayShell(Cmd):
    prompt = "Faraday> "
    intro = "Welcome to Faraday Cli! Type ? to list commands"
    doc_header = "Available Commands (type help <command>)"
    ruler = "-"

    emojis = {
        "cross": "\U0000274c",
        "check": "\U00002714",
        "arrow_up": "\U00002b06",
        "page": "\U0001f4c4",
        "laptop": "\U0001f4bb",
    }
    delattr(Cmd, "do_run_pyscript")
    delattr(Cmd, "do_run_script")

    def __init__(self, *args, **kwargs):
        super().__init__(
            persistent_history_file="~/.faraday-cli_history", *args, **kwargs
        )

        self.hidden_commands += ["EOF", "cd", "alias"]
        self.run_as_shell = False
        self.TABLE_PRETTY_FORMAT = "psql"
        # hide unwanted settings
        settings_to_hide = ["debug"]
        for setting_name in settings_to_hide:
            self.remove_settable(setting_name)
        intro = [style(logo, fg="red")]
        if active_config.faraday_url and active_config.token:
            intro.append(
                style(f"Server: {active_config.faraday_url}", fg="green")
            )
            self.api_client = FaradayApi(
                active_config.faraday_url,
                ignore_ssl=active_config.ignore_ssl,
                token=active_config.token,
            )
        else:
            self.api_client = FaradayApi()
            intro.append(
                style("Missing faraday server, run 'auth'", fg="yellow")
            )
        self.custom_plugins_path = active_config.custom_plugins_path
        self.ignore_info_severity = active_config.ignore_info_severity
        self.intro = "\n".join(intro)
        self.data_queue = queue.Queue()
        self.update_prompt()
        self.add_settable(
            Settable(
                "custom_plugins_path",
                str,
                "Path of custom plugins",
                onchange_cb=self._onchange_custom_plugins_path,
            )
        )
        self.add_settable(
            Settable(
                "ignore_info_severity",
                bool,
                "Ignore Informational vulnerabilities "
                "from reports and commands",
                onchange_cb=self._onchange_ignore_info_severity,
            )
        )
        self._create_plugin_manager()

    def _create_plugin_manager(self):
        self.plugins_manager = PluginsManager(
            self.custom_plugins_path, ignore_info=self.ignore_info_severity
        )
        self.report_analyzer = ReportAnalyzer(self.plugins_manager)
        self.command_analyzer = CommandAnalyzer(self.plugins_manager)

    def _onchange_custom_plugins_path(self, param_name, old, new):
        custom_plugins_path = Path(new)
        if custom_plugins_path.is_dir():
            active_config.custom_plugins_path = new
            active_config.save()
            self.custom_plugins_path = new
            self._create_plugin_manager()
        else:
            self.perror(f"Invalid Path: {new}")
            self.custom_plugins_path = old

    def _onchange_ignore_info_severity(self, param_name, old, new):
        active_config.ignore_info_severity = new
        active_config.save()
        self.ignore_info_severity = new
        self._create_plugin_manager()

    # Auth
    auth_parser = argparse.ArgumentParser()
    auth_parser.add_argument(
        "-f",
        "--faraday-url",
        type=str,
        help="Faraday server URL",
        required=False,
    )
    auth_parser.add_argument(
        "-i",
        "--ignore-ssl",
        action="store_true",
        help="Ignore SSL verification",
    )
    auth_parser.add_argument(
        "-u", "--user", type=str, help="Faraday user", required=False
    )
    auth_parser.add_argument(
        "-p", "--password", type=str, help="Faraday password", required=False
    )

    @with_argparser(auth_parser)
    def do_auth(self, args):
        """Authenticate with a faraday server"""
        faraday_url = args.faraday_url
        user = args.user
        password = args.password
        ignore_ssl = args.ignore_ssl
        if not faraday_url:
            faraday_url = utils.validate_url(
                click.prompt(
                    "\nFaraday url", default=active_config.faraday_url
                )
            )
            url_data = urlparse(faraday_url)
            if url_data.scheme == "https":
                ignore_ssl = (
                    click.prompt(
                        f"\nValidate SSL certificate for [{faraday_url}]",
                        type=click.Choice(
                            choices=["Y", "N"], case_sensitive=False
                        ),
                        default="Y",
                    )
                    == "N"
                )
        else:
            faraday_url = utils.validate_url(faraday_url)
        if not user:
            user = click.prompt("\nUser")
        if not password:
            password = click.prompt("\nPassword", hide_input=True)
        try:
            api_client = FaradayApi(faraday_url, ignore_ssl=ignore_ssl)
            login_ok = api_client.login(user, password)
            if login_ok is None or login_ok is True:
                if login_ok is None:
                    # 2FA Required
                    second_factor = click.prompt("2FA")
                else:
                    second_factor = None
                token = api_client.get_token(second_factor)
                active_config.faraday_url = faraday_url
                active_config.ignore_ssl = args.ignore_ssl
                active_config.token = token
                active_config.workspace = None
                active_config.save()
                self.api_client = FaradayApi(
                    faraday_url, ignore_ssl=ignore_ssl, token=token
                )
                self.poutput(style("Saving config", fg="green"))
                self.poutput(
                    style(
                        f"{self.emojis['check']} Authenticated with faraday: {faraday_url}",  # noqa: E501
                        fg="green",
                    )
                )
                self.update_prompt()
            else:
                self.perror("Invalid credentials")
                if self.run_as_shell:
                    sys.exit(1)
        except Invalid2FA:
            self.perror("Invalid 2FA")
            if self.run_as_shell:
                sys.exit(1)
        except InvalidCredentials:
            self.perror("Invalid credentials")
            if self.run_as_shell:
                sys.exit(1)
        except ClientError:
            self.perror("Invalid credentials")
            if self.run_as_shell:
                sys.exit(1)
        except ClientConnectionError as e:
            self.perror(f"Connection refused: {e} (check your Faraday server)")
            if self.run_as_shell:
                sys.exit(1)
        except Exception as e:
            self.perror(f"{e}")
            if self.run_as_shell:
                sys.exit(1)

    def do_exit(self, inp):
        """Exit shell"""
        self.poutput(style("Bye", fg="green"))
        return True

    def help_exit(self):
        print("exit the application. Shorthand: Ctrl-D.")

    def postcmd(self, stop, line):
        def send_to_faraday(ws, data):
            spinner = Halo(text="Sending", text_color="green", spinner="dots")
            spinner.start()
            self.api_client.bulk_create(ws, data)
            spinner.stop()

        while not self.data_queue.empty():
            data = self.data_queue.get()
            message = f"{self.emojis['arrow_up']} Sending data to workspace: {data['workspace']}"  # noqa: E501
            self.poutput(style(message, fg="green"))
            send_to_faraday(data["workspace"], data["json_data"])
            self.poutput(style(f"{self.emojis['check']} Done", fg="green"))

        return Cmd.postcmd(self, stop, line)

    def update_prompt(self) -> None:
        self.prompt = self.get_prompt()

    def get_prompt(self) -> str:
        if active_config.workspace:
            return style(f"[ws:{active_config.workspace}]> ", fg="blue")
        else:
            return style("Faraday> ", fg="blue")

    # Status
    status_parser = argparse.ArgumentParser()
    status_parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty Tables"
    )

    @with_argparser(status_parser)
    def do_status(self, args):
        """Show Cli status"""
        valid_token = self.api_client.is_token_valid()
        user = None
        version = "-"
        if valid_token:
            version_data = self.api_client.get_version()
            version = f"{version_data['product']}-{version_data['version']}"
            user = self.api_client.get_user()
        data = [
            {
                "FARADAY SERVER": active_config.faraday_url,
                "IGNORE SSL": active_config.ignore_ssl,
                "VERSION": version,
                "USER": user if user else "-",
                "VALID TOKEN": "\U00002714" if valid_token else "\U0000274c",
                "WORKSPACE": active_config.workspace,
            }
        ]
        self.poutput(
            style(
                tabulate(
                    data,
                    headers="keys",
                    tablefmt=self.TABLE_PRETTY_FORMAT
                    if args.pretty
                    else "simple",
                ),
                fg="green",
            )
        )

    # Run Command
    def run_command(self, plugin, user, command):
        current_path = os.path.abspath(os.getcwd())
        modified_command = plugin.processCommandString(
            getpass.getuser(), current_path, command
        )
        if modified_command:
            command = modified_command
        p = subprocess.Popen(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = io.StringIO()
        while True:
            retcode = p.poll()
            line = p.stdout.readline().decode("utf-8")
            sys.stdout.write(line)
            output.write(line)
            if retcode is not None:
                extra_lines = map(
                    lambda x: x.decode("utf-8"), p.stdout.readlines()
                )
                sys.stdout.writelines(line)
                output.writelines(extra_lines)
                break
        output_value = output.getvalue()
        if retcode == 0:
            plugin.processOutput(output_value)
            return plugin.get_data()
        else:
            return None

    def do_cd(self, path):
        """Change directory"""
        if not path:
            path = "~"
        cd_path = os.path.expanduser(path)
        if os.path.isdir(cd_path):
            os.chdir(cd_path)
        else:
            self.poutput(f"cd: no such file or directory: {path}")

    def default(self, statement: Statement):
        if not active_config.workspace:
            self.perror("No active Workspace")
            os.system(statement.raw)
        else:
            plugin = self.command_analyzer.get_plugin(statement.raw)
            if plugin:
                click.secho(
                    f"{self.emojis['laptop']} Processing {plugin.id} command",
                    fg="green",
                )
                command_json = utils.run_tool(
                    plugin, getpass.getuser(), statement.raw
                )
                if not command_json:
                    click.secho(
                        f"{self.emojis['cross']} Command execution error!!",
                        fg="red",
                    )
                else:
                    self.data_queue.put(
                        {
                            "workspace": active_config.workspace,
                            "json_data": command_json,
                        }
                    )
            else:
                os.system(statement.raw)
