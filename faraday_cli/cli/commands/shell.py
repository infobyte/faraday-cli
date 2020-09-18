# flake8: noqa
import os
import queue
from cmd import Cmd
from collections import OrderedDict
from pyfiglet import Figlet
import click
import getpass
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate
import subprocess
import shlex
import io
import sys

from faraday_cli.utils.halo.halo import Halo
from faraday_cli.config import active_config
from faraday_cli.cli import utils
from faraday_plugins.plugins.manager import (
    PluginsManager,
    CommandAnalyzer,
    ReportAnalyzer,
)


def run_command(plugin, user, command):
    current_path = os.path.abspath(os.getcwd())
    modified_command = plugin.processCommandString(
        getpass.getuser(), current_path, command
    )
    if modified_command:
        command = modified_command
    p = subprocess.Popen(
        shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
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


@click.command(help="Run faraday shell")
@click.option("-cpf", "--custom-plugins-folder", type=str)
@click.pass_obj
def shell(api_client, custom_plugins_folder):

    plugins_manager = PluginsManager(custom_plugins_folder)
    command_analyzer = CommandAnalyzer(plugins_manager)
    report_analyzer = ReportAnalyzer(plugins_manager)

    class FaradayShell(Cmd):
        __hiden_methods = ("do_EOF", "do_cd")
        prompt = "Faraday> "
        intro = "Welcome to Faraday Cli! Type ? to list commands"
        doc_header = "Available Commands (type help <command>)"
        ruler = "-"
        data_queue = queue.Queue()
        f = Figlet(font="slant")
        click.secho(f.renderText("Faraday Cli"), fg="red")
        click.secho(f"Server: {active_config.faraday_url}", fg="green")
        emojis = {
            "cross": "\U0000274c",
            "check": "\U00002714",
            "arrow_up": "\U00002b06",
            "page": "\U0001f4c4",
            "laptop": "\U0001f4bb",
        }

        def __init__(self):
            self.api_client = api_client
            super().__init__()

        def get_names(self):
            return [
                n for n in dir(self.__class__) if n not in self.__hiden_methods
            ]

        def do_exit(self, inp):
            """Exit"""
            click.secho("Bye", fg="green")
            return True

        def help_exit(self):
            print("exit the application. Shorthand: Ctrl-D.")

        def emptyline(self):
            return ""

        # def precmd(self, line):
        #     print('precmd(%s)' % line)
        #     original = Cmd.precmd(self, line)
        #     print(f"original {original}")
        #     return original

        def do_status(self, input):
            """Show Cli status"""
            click.secho(
                f"Server: {active_config.faraday_url} [Check SSL: {active_config.ssl_verify}]",
                fg="yellow",
            )
            click.secho(f"Token: {active_config.token}", fg="yellow")
            click.secho(f"Workspace: {active_config.workspace}", fg="yellow")

        def do_current_ws(self, input):
            """Show current workspace"""
            if active_config.workspace:
                click.secho(
                    f"Current workspace: {active_config.workspace}", fg="green"
                )
            else:
                click.secho(
                    f"{self.emojis['cross']} No workspace selected", fg="red"
                )

        def do_select_ws(self, workspace_name):
            """Select workspace"""
            if self.api_client.is_workspace_valid(workspace_name):
                active_config.workspace = workspace_name
                active_config.save()
                click.secho(
                    f"{self.emojis['check']} Selected workspace: {workspace_name}",
                    fg="green",
                )
            else:
                click.secho(
                    f"{self.emojis['cross']} Invalid workspace: {workspace_name}",
                    fg="red",
                )

        def do_list_ws(self, input):
            """List workspaces"""
            workspaces = self.api_client.get_workspaces()
            if not workspaces:
                click.secho(
                    f"{self.emojis['cross']} No workspaces available",
                    fg="yellow",
                )
            else:
                data = [
                    OrderedDict(
                        {
                            "name": x["name"],
                            "active": x["active"],
                            "public": x["public"],
                            "readonly": x["readonly"],
                            "hosts": x["stats"]["hosts"],
                            "services": x["stats"]["services"],
                            "vulns": x["stats"]["total_vulns"],
                        }
                    )
                    for x in workspaces
                ]
                click.secho(tabulate(data, headers="keys"), fg="yellow")

        def do_list_hosts(self, workspace_name):
            """List hosts in a workspace: list_hosts [ws]"""
            if workspace_name:
                if not self.api_client.is_workspace_valid(workspace_name):
                    click.secho(
                        f"{self.emojis['cross']} Invalid workspace: {workspace_name}",
                        fg="red",
                    )
                    return
                else:
                    workspace = workspace_name
            else:
                if not active_config.workspace:
                    click.secho(
                        f"{self.emojis['cross']} No workspace selected",
                        fg="red",
                    )
                    return
                else:
                    workspace = active_config.workspace
            hosts = self.api_client.get_hosts(workspace)
            click.secho(f"Workspace: {workspace}", fg="yellow")
            if not hosts["rows"]:
                click.secho(
                    f"{self.emojis['cross']} No hosts in workspace: {workspace}",
                    fg="yellow",
                )
            else:
                data = [
                    OrderedDict(
                        {
                            "id": x["value"]["id"],
                            "ip": x["value"]["ip"],
                            "os": x["value"]["os"],
                            "hostnames": ", ".join(x["value"]["hostnames"]),
                            "services": len(x["value"]["service_summaries"]),
                            "vulns": x["value"]["vulns"],
                        }
                    )
                    for x in hosts["rows"]
                ]
                click.secho(tabulate(data, headers="keys"), fg="yellow")

        def do_get_host(self, host_id):
            """Get host info"""
            if not active_config.workspace:
                click.secho("No workspace selected", fg="red")
                return
            else:
                workspace = active_config.workspace
            try:
                host = self.api_client.get_host(workspace, host_id)
            except NotFoundError:
                click.secho(f"{self.emojis['cross']} Host not found", fg="red")
                return

            host_data = [
                OrderedDict(
                    {
                        "id": x["id"],
                        "ip": x["ip"],
                        "os": x["os"],
                        "hostnames": ", ".join(x["hostnames"]),
                        "owner": x["owner"],
                        "owned": x["owned"],
                        "vulns": x["vulns"],
                    }
                )
                for x in [host]
            ]
            click.secho("Host:", fg="yellow")
            click.secho(tabulate(host_data, headers="keys"), fg="yellow")
            if host["services"] > 0:
                services = self.api_client.get_host_services(
                    workspace, host_id
                )
                services_data = [
                    OrderedDict(
                        {
                            "id": x["id"],
                            "name": x["name"],
                            "description": x["description"],
                            "protocol": x["protocol"],
                            "port": x["port"],
                            "version": x["version"],
                            "status": x["status"],
                            "vulns": x["vulns"],
                        }
                    )
                    for x in services
                ]
                click.secho("\nServices:", fg="yellow")
                click.secho(
                    tabulate(services_data, headers="keys"), fg="yellow"
                )
                if host["vulns"] > 0:
                    vulns = self.api_client.get_host_vulns(
                        workspace, host["ip"]
                    )
                    vulns_data = [
                        OrderedDict(
                            {
                                "id": x["id"],
                                "name": x["value"]["name"],
                                "description": utils.trim_long_text(
                                    x["value"]["description"]
                                ),
                                "severity": x["value"]["severity"],
                                "status": x["value"]["status"],
                                "parent": x["value"]["parent_type"],
                                "confirmed": x["value"]["confirmed"],
                                "tool": x["value"]["metadata"]["creator"],
                            }
                        )
                        for x in vulns["vulnerabilities"]
                    ]
                    click.secho("\nVulnerabilities:", fg="yellow")
                    click.secho(
                        tabulate(vulns_data, headers="keys"), fg="yellow"
                    )

        def postcmd(self, stop, line):
            @Halo(text="Sending", text_color="green", spinner="dots")
            def send_to_faraday(ws, data):
                self.api_client.bulk_create(ws, data)

            while not self.data_queue.empty():
                data = self.data_queue.get()
                message = f"{self.emojis['arrow_up']} Sending data to workspace: {data['workspace']}"
                click.secho(message, fg="green")
                send_to_faraday(data["workspace"], data["json_data"])
                click.secho(f"{self.emojis['check']} Done", fg="green")

            return Cmd.postcmd(self, stop, line)

        def do_cd(self, path):
            """Change directory"""
            if not path:
                path = "~"
            cd_path = os.path.expanduser(path)
            if os.path.isdir(cd_path):
                os.chdir(cd_path)
            else:
                click.echo(f"cd: no such file or directory: {path}")

        def do_load_report(self, report_path):
            """Load tool report into faraday"""
            if not active_config.workspace:
                click.style(
                    f"{self.emojis['cross']} No workspace selected", fg="red"
                )
                return
            report_path = os.path.expanduser(report_path)
            if os.path.isfile(report_path):
                plugin = report_analyzer.get_plugin(report_path)
                if not plugin:
                    click.echo(
                        click.style(
                            f"{self.emojis['cross']} Failed to detect report: {report_path}",
                            fg="red",
                        ),
                        err=True,
                    )
                else:
                    click.secho(
                        f"{self.emojis['page']} Processing {plugin.id} report",
                        fg="green",
                    )
                    plugin.processReport(report_path, getpass.getuser())
                    self.data_queue.put(
                        {
                            "workspace": active_config.workspace,
                            "json_data": plugin.get_data(),
                        }
                    )

        def do_create_ws(self, workspace_name):
            """Create workspace | create_ws workspace_name"""
            if not workspace_name:
                click.secho(
                    f"{self.emojis['cross']} Workspace name required", fg="red"
                )
                return
            try:
                self.api_client.create_workspace(workspace_name)
            except Exception as e:
                click.secho(f"{self.emojis['cross']} - {e}", fg="red")
            else:
                click.secho(
                    f"{self.emojis['check']} Created workspace: {workspace_name}",
                    fg="green",
                )

        def default(self, input):
            plugin = command_analyzer.get_plugin(input)
            if plugin:
                click.secho(
                    f"{self.emojis['laptop']} Processing {plugin.id} command",
                    fg="green",
                )
                command_json = run_command(plugin, getpass.getuser(), input)
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
                os.system(input)

        do_EOF = do_exit
        help_EOF = help_exit

    FaradayShell().cmdloop()
