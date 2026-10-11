"""Default pentest/triage instructions for the `faradai` commands.

These are copied verbatim from the FaradAI wizard's staged instruction
templates (faraday.ai `dashboard/wizard/instruction_templates/*.md`) so the CLI
launches a run with the SAME default INSTRUCTION the web wizard sends:

    standard  scan      → standard.md
    advanced  scan      → full-audit.md
    triage              → triage.md

Keep these in sync with the wizard templates. The wizard sends GOAL only when
the operator fills the Context "focus areas" (empty by default), so the CLI
likewise sends GOAL only when the user passes --goal.
"""

# --- standard scan (wizard: standard.md) ------------------------------------
STANDARD_INSTRUCTION = """\
## Objective
Authenticated black/grey-box penetration test of the target web application(s)
and API(s). Find and prove exploitable vulnerabilities — do not just scan and
report. Chain findings into real attack paths and demonstrate impact.

Rules of engagement: only test the in-scope targets listed above. Use the
supplied test users / headers for authenticated surface. Stop at the minimum
provable impact for any state-changing or data-access action; never damage data
or pivot to out-of-scope systems.

## Attack path
**Stage 0 — Recon & mapping.** Enumerate the attack surface: subdomains, live
hosts, open ports, technologies, and every reachable endpoint. Map the
authenticated vs. unauthenticated surface. Record the app's normal behavior so
anomalies stand out later.

**Stage 1 — Authentication & session.** Test the auth flows with the supplied
test users: session fixation, weak/reused tokens, JWT flaws, password reset
abuse, MFA bypass. Establish an authenticated session for deeper testing.

**Stage 2 — Access control.** For every authenticated feature, test horizontal
and vertical privilege escalation (IDOR, forced browsing, missing
function-level auth). Use the second test user (if provided) to prove
cross-user data access.

**Stage 3 — Injection & input handling.** SQLi, command injection, SSTI, XXE,
path traversal, SSRF, and both stored and reflected XSS across every input.
Prioritise inputs that reach a database, the filesystem, or an internal service.

**Stage 4 — Business logic & chaining.** Abuse workflows (payment, checkout,
provisioning, rate limits). Chain lower-severity findings from earlier stages
into a high-impact path — e.g. an info leak that reveals a token that unlocks
an IDOR.

## Focus & priorities
(Add per-engagement focus in the Context step — which flows matter most, the
business risks that would hurt most, known weak spots.)"""

# --- advanced scan (wizard: full-audit.md) ----------------------------------
ADVANCED_INSTRUCTION = """\
## Objective
Comprehensive audit — combine a white-box source-code review with a live
authenticated pentest into one engagement. Use knowledge from the code to drive
sharper exploitation against the running target, and confirm code-level
findings against the live deployment. Produce an auditor-ready set of proven,
exploitable findings.

## Attack path
**Stage 0 — Dual recon.** Map the live attack surface AND orient in the source
tree. Cross-reference: which routes in the code map to which live endpoints,
which config values are live, which auth model is deployed.

**Stage 1 — Code-informed secrets & auth.** From the source, extract secrets,
auth logic, and token formats. Immediately validate them against the live
target — a hardcoded key or a weak JWT secret found in code becomes a live
authentication bypass.

**Stage 2 — Traced injection.** Use the code to find injection sinks, then
prove each against the running app. The source tells you the exact parameter
and the exact query — the live test proves impact.

**Stage 3 — Access control, both sides.** Every authorization check in the code
is a live IDOR/privilege-escalation candidate. Prove cross-user and cross-role
access on the deployment with the supplied test users.

**Stage 4 — Business logic & full chains.** Chain code-level insight with live
exploitation into complete, high-impact attack paths. This is where the audit
earns its depth: a config leak → a token format from code → a live IDOR →
cross-tenant data access.

## Focus & priorities
(Add per-engagement focus in the Context step — the highest-risk flows and the
components where code and deployment should be cross-checked first.)"""

# --- triage (wizard: triage.md) ---------------------------------------------
TRIAGE_INSTRUCTION = """\
## Objective
Time-boxed triage pentest of the target. Budget: 4 rounds / 2 hours. Prioritise
high-probability, high-impact findings over exhaustive coverage. Prove at least
one critical or high finding if one exists; stop at minimum reproducible proof.

Rules of engagement: only test the in-scope targets listed above. Use the
supplied test users / headers for authenticated surface. Stop at the minimum
provable impact for any state-changing or data-access action.

## Attack path
**Stage 0 — Rapid surface mapping.** Enumerate subdomains, live hosts, and the
top endpoints in 1 round. Record the tech stack and authentication surface.

**Stage 1 — High-value auth & access checks.** Test login flows, session tokens,
and one horizontal privilege escalation (IDOR) with the supplied test users.
Stop as soon as a critical auth bypass or cross-user data leak is proved.

**Stage 2 — Top injection vectors.** SQLi, SSRF, and SSTI on the highest-risk
inputs (search, filters, file-upload, URL parameters). Prioritise inputs that
reach a database or internal service.

**Stage 3 — Chain & report.** Link any found issues into a single attack path
showing real business impact. File all findings — even low severity — so the
operator can decide follow-up depth.

## Focus & priorities
(Add per-engagement focus in the Context step — which flows matter most, the
business risks that would hurt most, known weak spots.)"""

# Scan-tier → instruction (standard default is 20 rounds, advanced is 80).
SCAN_INSTRUCTIONS = {
    "standard": STANDARD_INSTRUCTION,
    "advanced": ADVANCED_INSTRUCTION,
}
