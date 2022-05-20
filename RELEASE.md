2.1.3 [May 20th, 2022]:
---
 * ADD possibility to avoid resolve hostname by changing resolve_hostname parameter
 * Fix the colors in Severity Stats

2.1.2 [Jan 11th, 2022]:
---
 * Update Documentation
 * Workaround for api bug

2.1.1 [Dec 13th, 2021]:
---
 * ADD setting to enable/disable auto command detection
 * Fix error message when a command dont generate valid output
 * FIX tables visualization when host has to many hostnames
 * Show if update is available

2.1.0 [Nov 19th, 2021]:
---
 * Add fields to executive reports generation command
 * Add KAKER_MODE easter egg
 * update plugins requirements to 1.5.6

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
