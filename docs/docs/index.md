# Faraday Cli

Use [Faraday](https://faradaysec.com/) directly from your favorite terminal. faraday-cli is the official client that make automating your security workflows, easier.

<script src="https://asciinema.org/a/384132.js" id="asciicast-384132" async data-autoplay="false" data-size="small"></script>


# Examples

Here you have some snippets of different workflows you can generate using faraday-cli

#### One-line Continuous Scan

Scan assets from workspace.

```shell
$ faraday-cli host list -ip -w other_ws | nmap -iL - -oX /tmp/nmap.xml && faraday-cli tool report -w other_ws /tmp/nmap.xml
```

### One-Line to nmap to all the host in the workspace and import the results back to Faraday

To scan all the host list inside a workspace with ```nmap``` and import the results back to faraday.

```shell
for ip in $(faraday-cli host list -ip); faraday-cli tool run \"nmap -Pn -p443,80 -sV --script=+http-enum -vvv $ip\"
```



!!! info In this case it should have a workspace named "other_ws" with  hostnames in it

#### Scan your subdomains

Use a tool like ```assetfinder``` to do a domains lookup, scan them with nmap and send the results to faraday

```shell
$ assetfinder -subs-only example.com| sort | uniq |awk 'BEGIN { ORS = ""; print " {\"target\":\""}
{ printf "%s%s", separator, $1, $2
separator = ","}END { print "\"}" }' | faraday-cli agent run -a 1 -e nmap --stdin
```
!!! info For this purpouse, an agent is created and already connected to run the nmap executor

#### Send Faraday Executive Reports by mail

Run a daily scan and send your report

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


!!! question "Too many secrets?"
```
QW55IGZhbnMgb2YgVGhlIFNuZWFrZXJzPz8gVHJ5IHJ1bm5pbmcgZmFyYWRheS1jbGkgYWZ0ZXIgc2V0dGluZyB0aGlzICJleHBvcnQgS0FLRVJfTU9ERT0xIg
```
