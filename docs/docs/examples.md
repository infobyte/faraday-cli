
Here you have some snippets of different workflows you can generate using faraday-cli

#### Load your assets from your cloud provider

Here you can list your assets using a cli from your provider (in this example Digital Ocean), then generate a json with that information and use faraday-cli to send it to faraday.

```shell
$ doctl compute droplet list --format PublicIPv4,Name --no-header | awk 'BEGIN { ORS = ""; print " ["}
{ printf "%s{\"ip\": \"%s\", \"description\": \"%s\"}", separator, $1, $2
separator = ", "}END { print "] " }' | faraday-cli create_hosts --stdin
```


#### Scan assets from workspace

Take assets form a workspace, scan them with nmap and send the results to other workspace

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
