# Faraday Cli

Faraday Cli is a command line tool that let you use [Faraday](https://faradaysec.com/) directly from your favorite terminal.

Use [Faraday](https://faradaysec.com/) directly from your favorite terminal. faraday-cli is the official client that make automating your security workflows, easier.

<script src="https://asciinema.org/a/384132.js" id="asciicast-384132" async data-autoplay="false" data-size="small"></script>



# Examples

Here you have some snippets of different workflows you can generate using faraday-cli

#### One-line Continuous Scan

Scan assets from workspace.

```shell
$ faraday-cli list_hosts -ip | nmap -iL - -oX /tmp/nmap.xml && faraday-cli process_report -w other_ws /tmp/nmap.xml
```

#### Scan your subdomains

Use a tool like ```assetfinder``` to do a domains lookup, scan them with nmap and send de results to faraday

```shell
$ assetfinder -subs-only example.com| sort | uniq |awk 'BEGIN { ORS = ""; print " {\"target\":\""}
{ printf "%s%s", separator, $1, $2
separator = ","}END { print "\"}" }' | faraday-cli  run_executor -a 1 -e nmap --stdin
```

#### Send Faraday Executive Reports by mail

Run a dalily scan and send your report

```shell
$ faraday-cli generate_executive_report -t \'"generic_default.docx (generic)"\' --confirmed -o /tmp/report.docx && echo "Faraday Daily Report" | mail -s "Daily Report" user@example.com -A /tmp/report.docx
```

#### Load your assets from your cloud provider

Here you can list your assets using a cli from your provider (in this example Digital Ocean), then generate a json with that information and use faraday-cli to send it to faraday.

```shell
$ doctl compute droplet list --format PublicIPv4,Name --no-header | awk 'BEGIN { ORS = ""; print " ["}
{ printf "%s{\"ip\": \"%s\", \"description\": \"%s\"}", separator, $1, $2
separator = ", "}END { print "] " }' | faraday-cli create_hosts --stdin
```
