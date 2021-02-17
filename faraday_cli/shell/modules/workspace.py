import json
import argparse
from collections import OrderedDict

from cmd2 import style, with_argparser, with_default_category, CommandSet
from simple_rest_client.exceptions import NotFoundError
from tabulate import tabulate

from faraday_cli.config import active_config


@with_default_category("Workspaces")
class WorkspaceCommands(CommandSet):
    def __init__(self):
        super().__init__()

    select_ws_parser = argparse.ArgumentParser()
    select_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )

    @with_argparser(select_ws_parser)
    def do_select_ws(self, args):
        """Select active Workspace"""
        if self._cmd.api_client.is_workspace_valid(args.workspace_name):
            active_config.workspace = args.workspace_name
            active_config.save()
            self._cmd.poutput(
                style(
                    f"{self._cmd.emojis['check']} "
                    f"Selected workspace: {args.workspace_name}",
                    fg="green",
                )
            )
            self._cmd.update_prompt()
        else:
            self._cmd.perror(
                f"{self._cmd.emojis['cross']} "
                f"Invalid workspace: {args.workspace_name}"
            )

    list_ws_parser = argparse.ArgumentParser()
    list_ws_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    list_ws_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )
    list_ws_parser.add_argument(
        "--show-inactive", action="store_true", help="Show inactive workspaces"
    )

    @with_argparser(list_ws_parser)
    def do_list_ws(self, args):
        """List Workspaces"""
        workspaces = self._cmd.api_client.get_workspaces(
            get_inactives=args.show_inactive
        )
        if args.json_output:
            self._cmd.poutput(json.dumps(workspaces, indent=4))
            return
        else:
            if not workspaces:
                self._cmd.poutput("No workspaces available")
                return
            else:
                data = [
                    OrderedDict(
                        {
                            "NAME": x["name"],
                            "HOSTS": x["stats"]["hosts"],
                            "SERVICES": x["stats"]["services"],
                            "VULNS": "-"
                            if x["stats"]["total_vulns"] == 0
                            else x["stats"]["total_vulns"],
                            "ACTIVE": x["active"],
                            "PUBLIC": x["public"],
                            "READONLY": x["readonly"],
                        }
                    )
                    for x in workspaces
                ]
                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                        if args.pretty
                        else "simple",
                    )
                )

    get_ws_parser = argparse.ArgumentParser()
    get_ws_parser.add_argument(
        "-w",
        "--workspace-name",
        type=str,
        help="Workspace name",
        required=False,
    )
    get_ws_parser.add_argument(
        "-j", "--json-output", action="store_true", help="Show output in json"
    )
    get_ws_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Show table in a pretty format",
    )

    @with_argparser(get_ws_parser)
    def do_get_ws(self, args):
        """Get Workspace"""
        if not args.workspace_name:
            if active_config.workspace:
                workspace_name = active_config.workspace
            else:
                self._cmd.perror("No active Workspace")
                return
        else:
            workspace_name = args.workspace_name
        try:
            workspace = self._cmd.api_client.get_workspace(workspace_name)
        except NotFoundError:
            self._cmd.perror(f"Workspace {workspace_name} not found")
        else:
            if args.json_output:
                self._cmd.poutput(json.dumps(workspace, indent=4))
                return
            else:
                data = [
                    {
                        "NAME": workspace["name"],
                        "ACTIVE": workspace["active"],
                        "PUBLIC": workspace["public"],
                        "READONLY": workspace["readonly"],
                        "HOSTS": "-"
                        if workspace["stats"]["hosts"] == 0
                        else workspace["stats"]["hosts"],
                        "SERVICES": "-"
                        if workspace["stats"]["services"] == 0
                        else workspace["stats"]["services"],
                        "VULNS": "-"
                        if workspace["stats"]["total_vulns"] == 0
                        else workspace["stats"]["total_vulns"],
                    }
                ]
                self._cmd.poutput(
                    tabulate(
                        data,
                        headers="keys",
                        tablefmt=self._cmd.TABLE_PRETTY_FORMAT
                        if args.pretty
                        else "simple",
                    )
                )

    delete_ws_parser = argparse.ArgumentParser()
    delete_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )

    @with_argparser(delete_ws_parser)
    def do_delete_ws(self, args):
        """Delete Workspace"""
        workspaces = self._cmd.api_client.get_workspaces()
        workspace_choices = [ws for ws in map(lambda x: x["name"], workspaces)]
        workspace_name = args.workspace_name
        if workspace_name not in workspace_choices:
            self._cmd.perror(f"Invalid workspace: {workspace_name}")
            return
        self._cmd.poutput(f"Deleting workspace: {workspace_name}")
        self._cmd.api_client.delete_workspace(workspace_name)
        self._cmd.poutput(
            style(f"Deleted workspace: {args.workspace_name}", fg="green")
        )
        if active_config.workspace == workspace_name:
            active_config.workspace = None
            active_config.save()
        self._cmd.update_prompt()

    create_ws_parser = argparse.ArgumentParser()
    create_ws_parser.add_argument(
        "workspace_name", type=str, help="Workspace name"
    )
    create_ws_parser.add_argument(
        "-d",
        "--dont-select",
        action="store_true",
        help="Dont select after create",
    )

    @with_argparser(create_ws_parser)
    def do_create_ws(self, args):
        """Create Workspace"""
        workspace_name = args.workspace_name
        try:
            self._cmd.api_client.create_workspace(workspace_name)
        except Exception as e:
            self._cmd.perror(f"{e}")
        else:
            self._cmd.poutput(
                style(
                    f"{self._cmd.emojis['check']} "
                    f"Created workspace: {args.workspace_name}",
                    fg="green",
                )
            )
            if not args.dont_select:
                active_config.workspace = workspace_name
                active_config.save()
                self._cmd.update_prompt()
