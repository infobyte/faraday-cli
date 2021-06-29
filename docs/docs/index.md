# Faraday Cli

Use [Faraday](https://faradaysec.com/) directly from your favorite terminal. faraday-cli is the official client that make automating your security workflows, easier.

<script src="https://asciinema.org/a/384132.js" id="asciicast-384132" async data-autoplay="false" data-size="small"></script>



# Examples

Here you have some snippets of different workflows you can generate using faraday-cli

#### One-line Continuous Scan

Scan assets from workspace.

```shell
$ faraday-cli host list -ip | nmap -iL - -oX /tmp/nmap.xml && faraday-cli tool report -w other_ws /tmp/nmap.xml
```

#### Scan your subdomains

Use a tool like ```assetfinder``` to do a domains lookup, scan them with nmap and send de results to faraday

```shell
$ assetfinder -subs-only example.com| sort | uniq |awk 'BEGIN { ORS = ""; print " {\"target\":\""}
{ printf "%s%s", separator, $1, $2
separator = ","}END { print "\"}" }' | faraday-cli agent run -a 1 -e nmap --stdin
```

#### Send Faraday Executive Reports by mail

Run a dalily scan and send your report

```shell
$ faraday-cli executive_report create -t \'"generic_default.docx (generic) (Word)"\' --confirmed -o /tmp/report.docx && echo "Faraday Daily Report" | mail -s "Daily Report" user@example.com -A /tmp/report.docx
```

#### Load your assets from your cloud provider

Here you can list your assets using a cli from your provider (in this example Digital Ocean), then generate a json with that information and use faraday-cli to send it to faraday.

```shell
$ doctl compute droplet list --format PublicIPv4,Name --no-header | awk 'BEGIN { ORS = ""; print " ["}
{ printf "%s{\"ip\": \"%s\", \"description\": \"%s\"}", separator, $1, $2
separator = ", "}END { print "] " }' | faraday-cli host create --stdin
```
