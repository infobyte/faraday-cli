# Global Configurations

You can list or change some settings from the cli itself.

```

$ faraday-cli set
+------------------------+----------+----------------------------------------------------------------------------------+
|          Name          |  Value   |                                   Description                                    |
+------------------------+----------+----------------------------------------------------------------------------------+
| allow_style            | Terminal | Allow ANSI text style sequences in output (valid values:Always, Never, Terminal) |
| always_show_hint       | False    | Display tab completion hint even when completion suggestions print               |
| auto_command_detection | True     | Enable/disable automatic command detection                                       |
| custom_plugins_path    | None     | Path of custom plugins folder                                                    |
| echo                   | False    | Echo command issued into output                                                  |
| editor                 | vim      | Program used by 'edit'                                                           |
| feedback_to_output     | False    | Include nonessentials in '|', '>' results                                        |
| hostname_resolution    | True     | Enable/disable hostname resolution                                               |
| ignore_info_severity   | False    | Ignore Informational vulnerabilities from reports and commands                   |
| max_completion_items   | 50       | Maximum number of CompletionItems to display during tab completion               |
| quiet                  | False    | Don't print nonessential feedback                                                |
| timing                 | False    | Report execution times                                                           |
+------------------------+----------+----------------------------------------------------------------------------------+

$ faraday-cli set hostname_resolution False
hostname_resolution - was: True
now: False
```