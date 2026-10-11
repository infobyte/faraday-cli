"""Default INSTRUCTION / GOAL for the `faradai` commands.

The FaradAI cloud-agent `INSTRUCTION` and `GOAL` params are validated server-side
as strings capped at 256 characters (faraday.black
``validate_agent_params`` → ``type_validate('string', ...)``). So these defaults
are intentionally short (≤256). They distill the web wizard's staged templates
(standard.md / full-audit.md / triage.md) into a one-paragraph brief — same
intent and coverage, not the full Stage 0-4 text the wizard sends over its
CAM-direct path (which isn't subject to the 256 cap).

Override any of them with --instruction / --goal for a custom run.
"""


def _check(mapping):
    """Fail fast at import if any default exceeds the server's 256-char cap."""
    for key, text in mapping.items():
        if len(text) > 256:
            raise ValueError(f"faradai default {key!r} is {len(text)} chars (>256 server cap)")
    return mapping


# --- scan INSTRUCTION per tier (≤256) ---------------------------------------
STANDARD_INSTRUCTION = (
    "Authenticated black-box web+API pentest. PROVE exploitable bugs, don't just "
    "scan: auth/session, access control (IDOR/privesc), injection "
    "(SQLi/SSRF/XSS/SSTI), business logic. Chain into real attack paths. "
    "In-scope only; stop at minimum impact."
)

ADVANCED_INSTRUCTION = (
    "Comprehensive audit: source review + live authenticated pentest. From code, "
    "find secrets, auth logic and injection sinks, then PROVE each on the running "
    "target. Chain code insight + live exploitation into full high-impact attack "
    "paths. In-scope only."
)

# --- triage INSTRUCTION (≤256) ----------------------------------------------
TRIAGE_INSTRUCTION = (
    "Time-boxed triage of existing workspace findings. Re-test and reproduce "
    "high-probability, high-impact issues; prove at least one critical/high if "
    "present. Confirm or close false positives. In-scope only; stop at minimum "
    "reproducible proof."
)

# --- scan GOAL per tier (≤256) ----------------------------------------------
STANDARD_GOAL = (
    "Prove the highest-impact exploitable vulns and chain them into real attack "
    "paths: auth bypass, cross-user data access, injection reaching data/host/"
    "internal services."
)

ADVANCED_GOAL = (
    "Cross-check code vs live deployment to prove deep chained paths: "
    "code-sourced secrets/auth flaws and injection sinks confirmed live, "
    "escalated to cross-tenant or host-level impact."
)

# Scan-tier → (instruction, goal).
SCAN_INSTRUCTIONS = _check(
    {
        "standard": STANDARD_INSTRUCTION,
        "advanced": ADVANCED_INSTRUCTION,
    }
)
SCAN_GOALS = {
    "standard": STANDARD_GOAL,
    "advanced": ADVANCED_GOAL,
}

# Validate all strings against the cap at import.
_check(
    {
        "STANDARD_INSTRUCTION": STANDARD_INSTRUCTION,
        "ADVANCED_INSTRUCTION": ADVANCED_INSTRUCTION,
        "TRIAGE_INSTRUCTION": TRIAGE_INSTRUCTION,
        "STANDARD_GOAL": STANDARD_GOAL,
        "ADVANCED_GOAL": ADVANCED_GOAL,
    }
)
