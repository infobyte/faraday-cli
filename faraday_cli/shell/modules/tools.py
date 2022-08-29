import getpass
import json

import cmd2
from cmd2 import Fg as COLORS
from faraday_cli.config import active_config
from faraday_cli.shell import utils


@cmd2.with_default_category("Tools execution")
class ToolCommands(cmd2.CommandSet):
    def __init__(self):
        super().__init__()

    tool_parser = cmd2.Cmd2ArgumentParser()
    tool_parser.add_argument(
        "-w", "--workspace-name", type=str, help="Workspace"
    )
    tool_parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create the workspace it not exists",
    )
    tool_parser.add_argument(
        "--plugin-id",
        type=str,
        help="Plugin ID (force detection)",
        required=False,
    )
    tool_parser.add_argument(
        "-j",
        "--json-output",
        action="store_true",
        help="Show output in json (dont send it to faraday)",
    )
    tool_parser.add_argument(
        "--vuln-tag",
        type=str,
        help="Tag to add to vulnerabilities",
        required=False,
        action="append",
    )
    tool_parser.add_argument(
        "--host-tag",
        type=str,
        help="Tag to add to hosts",
        required=False,
        action="append",
    )
    tool_parser.add_argument(
        "--service-tag",
        type=str,
        help="Tag to add to services",
        required=False,
        action="append",
    )
    tool_parser.add_argument("command", help="Command of the tool to process")

    @cmd2.as_subcommand_to(
        "tool", "run", tool_parser, help="run a tool and process it"
    )
    def process_tool(self, args):
        """Process Tool execution in Faraday"""
        if not args.json_output:
            if not args.workspace_name:
                if active_config.workspace:
                    workspace_name = active_config.workspace
                else:
                    self._cmd.perror("No active Workspace")
                    return
            else:
                workspace_name = args.workspace_name
            if not self._cmd.api_client.is_workspace_available(workspace_name):
                if not args.create_workspace:
                    self._cmd.perror(f"Invalid workspace: {workspace_name}")
                    return
                else:
                    try:
                        self._cmd.api_client.create_workspace(workspace_name)
                        self._cmd.poutput(
                            cmd2.style(
                                f"Workspace {workspace_name} created",
                                fg=COLORS.GREEN,
                            )
                        )
                    except Exception as e:
                        self._cmd.perror(f"Error creating workspace: {e}")
                        return
                    else:
                        destination_workspace = workspace_name
            else:
                destination_workspace = workspace_name

        if args.plugin_id:
            plugin = self._cmd.plugins_manager.get_plugin(args.plugin_id)
            if not plugin:
                self._cmd.perror(f"Invalid Plugin: {args.plugin_id}")
                return
        else:
            plugin = self._cmd.command_analyzer.get_plugin(args.command)

        if plugin:
            if not args.json_output:
                self._cmd.poutput(
                    cmd2.style(
                        f"{self._cmd.emojis['laptop']} "
                        f"Processing {plugin.id} command",
                        fg=COLORS.GREEN,
                    )
                )
            plugin.vuln_tag = args.vuln_tag
            plugin.host_tag = args.host_tag
            plugin.service_tag = args.service_tag
            show_command_output = not args.json_output
            command_json = utils.run_tool(
                plugin,
                getpass.getuser(),
                args.command,
                show_output=show_command_output,
            )
            if not command_json:
                self._cmd.perror(
                    f"{self._cmd.emojis['cross']} Command execution error!!"
                )
            else:
                if args.json_output:
                    self._cmd.poutput(json.dumps(command_json, indent=4))
                else:
                    self._cmd.data_queue.put(
                        {
                            "workspace": destination_workspace,
                            "json_data": command_json,
                        }
                    )
        else:
            self._cmd.perror(
                f"Could not detect plugin for command: {args.command}"
            )
