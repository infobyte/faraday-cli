2.1.12 [Jan 6th, 2025]:
---
 * [MOD] Updated report generation to support multiple workspaces. #89

2.1.11 [Feb 26th, 2024]:
---
 * [FIX] Fixed workspace activation. #87

2.1.10 [Apr 5th, 2023]:
---
 * [MOD] Change resolve_hostname to false for default, add the --resolve-hostname flag for host create and add --force flag to tool run to process the output of the command regardless of the return code. #79

2.1.9 [Dec 15th, 2022]:
---
 * [ADD] Add vuln delete vuln-id.


2.1.8 [OCt 27th, 2022]:
---
 * [ADD] New method to update existing vuln.

2.1.7 [Sep 13th, 2022]:
---
 * Add personal status.
 * Replace the apply_tag function with plugins parameters.
 * Update agents docs.

2.1.6 [Jul 26th, 2022]:
---
 * Remove workspace from get/list agent and add it to run agent.

2.1.5 [Jun 10th, 2022]:
---
 * Now shell mode doesn't exit if it has faraday's url and token but the server is down.
 * Support multiple tags on import and run.
 * Update gifs of readme.

2.1.4 [May 23th, 2022]:
---
 * Check if token is valid on start in shell mode.

2.1.3 [May 20th, 2022]:
---
 * Now is possible to doesn't resolve hostname by changing resolve_hostname parameter.
 * Fix the colors in Severity Stats.

2.1.2 [Jan 11th, 2022]:
---
 * Update Documentation.

2.1.1 [Dec 13th, 2021]:
---
 * ADD setting to enable/disable auto command detection.
 * Fix error message when a command dont generate valid output.
 * FIX tables visualization when host has to many hostnames.
 * Show if update is available.

2.1.0 [Nov 19th, 2021]:
---
 * Add fields to executive reports generation command.
 * Add KAKER_MODE easter egg.
 * Update plugins requirements to 1.5.6

2.0.2 [Aug 9th, 2021]:
---
 * add --create-workspace parameter for tool command
 * Ask for executive report template if not provided
 * Add for executor parameters if not provided
 * [FIX] Bug using an invalid executor name
 * Update readme to fix some examples

2.0.1 [Jun 29th, 2021]:
---
 * [FIX] Show help if no subcommand is provided

2.0.0 [Jun 29th, 2021]:
---
 * [MOD] Change commands to verbs
 * Enable and disable Workspaces
 * Fix to use cmd2 2.0 and update requirements
 * Show message if license is expired
 * [MOD] Change to V3 api of faraday
 * Add command to upload evidence to vuln

1.1.1 [Jun 9th, 2021]:
---
 * Fix to use cmd2 2.0 and update requirements
 * Show message if license is expired
 * [MOD] Change to V3 api of faraday

1.1.0 [Apr 16th, 2021]:
---
 * Add new command to process a tool execution
 * Add command to list vulnerabilities
 * Add versions to dependencies
 * Add setting to ignore INFO vulns
 * Show only active workspaces by default unless you use the --show-inactive parameter
 * [MOD] Add support for tags
 * Update faraday_plugins version dependency
 * Fix create_hosts docs typo
 * Show user in status
 * [MOD] Update faraday-plugins

1.0.2 [Feb 17th, 2021]:
---
 * ADD documentation (made with mkdocs)
 * MOD Convert some command and help to plural
 * FIX Exit shell in case of invalid authorization result
 * FIX faraday 3.14.1 updated security lib, and make login bugged

1.0.1 [Jan 4th, 2021]:
---
 * Fix error in list_host command

1.0.0 [Dec 28th, 2020]:
---
 * Add List Services command
 * Change the import command/report message
 * Add support for executive reports
 * Show in status if token is valid

0.1.0 [Aug 28th, 2020]:
---
 * First version released, use with caution as it is still beta phase.
 * Access a faraday server from your CLI, your CI o any other bash interpreter.

