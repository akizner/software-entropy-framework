#!/usr/bin/env python3
"""
Entropy Framework — JIRA SWR (Sanctioned Work Ratio) Extraction & Analysis
===========================================================================

Extracts JIRA ticket data and computes Sanctioned Work Ratio using:
  1. Reporter vs Assignee heuristic (self-created = reporter == assignee)
  2. Parent lineage traversal (walk up issue hierarchy for authority inheritance)

Pipeline:
  Step 1: Extract JIRA tickets referenced in GitHub PR data
  Step 2: For each ticket, fetch reporter, assignee, parent chain from JIRA API
  Step 3: Classify each ticket's authority level
  Step 4: Compute per-engineer SWR using PR-to-ticket linkage

Authentication:
  Set environment variables:
    JIRA_URL=https://your-org.atlassian.net
    JIRA_EMAIL=your-email@company.com
    JIRA_API_TOKEN=your_jira_api_token

    # Comma-separated JIRA project keys to match in PR titles/branches:
    JIRA_PROJECTS=PROJ1,PROJ2

Usage:
    # Dry run — show which tickets would be fetched, no API calls:
    python extract_jira_swr.py dry-run

    # Extract JIRA data for all tickets referenced in PRs:
    python extract_jira_swr.py extract

    # Analyze SWR per engineer:
    python extract_jira_swr.py analyze

    # Full pipeline:
    python extract_jira_swr.py all
"""

import json
import os
import re
import sys
import time
import base64
import urllib.request
import urllib.error
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path(__file__).parent.parent / "data")))
JIRA_DIR = DATA_DIR / "_jira"
JIRA_TICKETS_DIR = JIRA_DIR / "tickets"

JIRA_BASE_URL = os.environ.get("JIRA_URL", "")
JIRA_API_BASE = f"{JIRA_BASE_URL}/rest/api/3" if JIRA_BASE_URL else ""

# Custom field IDs vary by JIRA instance. Override via env vars if yours differ.
JIRA_FIELD_EPIC_LINK = os.environ.get("JIRA_FIELD_EPIC_LINK", "customfield_10014")
JIRA_FIELD_STORY_POINTS = os.environ.get("JIRA_FIELD_STORY_POINTS", "customfield_10008")

# JIRA project keys — prevents false positives from CVE-*, ISO-*, etc.
_projects_env = os.environ.get("JIRA_PROJECTS", "")
JIRA_PROJECTS = set(p.strip() for p in _projects_env.split(",") if p.strip()) if _projects_env else set()

if not JIRA_PROJECTS:
    print("WARNING: JIRA_PROJECTS not set. Set to comma-separated project keys (e.g., PROJ1,PROJ2)")

# Ticket reference regex — matches PROJECT-12345 in PR titles/branches
if JIRA_PROJECTS:
    TICKET_PATTERN = re.compile(r"\b(" + "|".join(re.escape(p) for p in JIRA_PROJECTS) + r")-(\d+)\b")
else:
    # Fallback: match any UPPERCASE-digits pattern (higher false-positive risk)
    TICKET_PATTERN = re.compile(r"\b([A-Z]{2,10})-(\d+)\b")

# Max parent depth to traverse (prevent infinite loops on circular refs)
MAX_PARENT_DEPTH = 10

# Rate limiting
REQUEST_DELAY = 0.1
RATE_LIMIT_PAUSE = 60

# Optional: repos to exclude from analysis (comma-separated env var)
_excluded_env = os.environ.get("EXCLUDED_REPOS", "")
EXCLUDED_REPOS = set(r.strip() for r in _excluded_env.split(",") if r.strip()) if _excluded_env else set()

# Optional: filter to specific GitHub logins (comma-separated env var)
# If not set, analyzes all authors found in the data.
_target_env = os.environ.get("TARGET_LOGINS", "")
TARGET_LOGINS = {}
if _target_env:
    # Format: login1:Display Name,login2:Display Name
    for entry in _target_env.split(","):
        entry = entry.strip()
        if ":" in entry:
            login, name = entry.split(":", 1)
            TARGET_LOGINS[login.strip()] = name.strip()
        elif entry:
            print(f"WARNING: TARGET_LOGINS entry '{entry}' missing ':DisplayName'. Fallback may fail.")
            TARGET_LOGINS[entry] = entry

BOT_SUFFIXES = ("[bot]",)


def is_bot(login):
    if not login:
        return True
    return any(login.endswith(s) for s in BOT_SUFFIXES)


# ── JIRA API ────────────────────────────────────────────────────────────────

def get_jira_auth():
    """Build Basic Auth header from environment variables."""
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        print("ERROR: Set JIRA_EMAIL and JIRA_API_TOKEN environment variables")
        print("  export JIRA_EMAIL=your-email@company.com")
        print("  export JIRA_API_TOKEN=your_jira_api_token")
        sys.exit(1)
    if not JIRA_BASE_URL:
        print("ERROR: Set JIRA_URL environment variable")
        print("  export JIRA_URL=https://your-org.atlassian.net")
        sys.exit(1)
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}


def jira_get(path, headers):
    """GET request to JIRA API with retry on rate limit."""
    url = f"{JIRA_API_BASE}{path}"
    req = urllib.request.Request(url, headers=headers, method="GET")

    for attempt in range(3):
        try:
            time.sleep(REQUEST_DELAY)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  Rate limited, pausing {RATE_LIMIT_PAUSE}s...")
                time.sleep(RATE_LIMIT_PAUSE)
                continue
            elif e.code == 404:
                return None
            elif e.code == 403:
                print(f"  Permission denied for {path}")
                return None
            else:
                print(f"  HTTP {e.code} for {path}: {e.reason}")
                if attempt == 2:
                    return None
                time.sleep(5)
        except Exception as e:
            print(f"  Network error for {path}: {e}")
            if attempt == 2:
                return None
            time.sleep(5)
    return None


def fetch_ticket(ticket_key, headers):
    """Fetch a single JIRA ticket with fields needed for SWR analysis."""
    fields = ",".join([
        "summary",
        "reporter",
        "assignee",
        "issuetype",
        "status",
        "parent",
        "created",
        "project",
        "labels",
        "priority",
        JIRA_FIELD_EPIC_LINK,
        JIRA_FIELD_STORY_POINTS,
    ])

    data = jira_get(f"/issue/{ticket_key}?fields={fields}", headers)
    if not data:
        return None

    fields_data = data.get("fields", {})

    reporter_obj = fields_data.get("reporter") or {}
    reporter = reporter_obj.get("accountId", "")
    reporter_display = reporter_obj.get("displayName", "unknown")
    reporter_email = reporter_obj.get("emailAddress", "")

    assignee_obj = fields_data.get("assignee") or {}
    assignee = assignee_obj.get("accountId", "")
    assignee_display = assignee_obj.get("displayName", "unassigned")
    assignee_email = assignee_obj.get("emailAddress", "")

    parent_obj = fields_data.get("parent") or {}
    parent_key = parent_obj.get("key")
    parent_summary = (parent_obj.get("fields") or {}).get("summary", "")
    parent_type = ((parent_obj.get("fields") or {}).get("issuetype") or {}).get("name", "")

    issuetype_obj = fields_data.get("issuetype") or {}
    issue_type = issuetype_obj.get("name", "")
    is_subtask = issuetype_obj.get("subtask", False)

    epic_link = fields_data.get(JIRA_FIELD_EPIC_LINK) or ""

    project_obj = fields_data.get("project") or {}
    project_key = project_obj.get("key", "")

    return {
        "key": ticket_key,
        "summary": fields_data.get("summary", ""),
        "issue_type": issue_type,
        "is_subtask": is_subtask,
        "status": (fields_data.get("status") or {}).get("name", ""),
        "project": project_key,
        "created": fields_data.get("created", ""),
        "reporter_id": reporter,
        "reporter_name": reporter_display,
        "reporter_email": reporter_email,
        "assignee_id": assignee,
        "assignee_name": assignee_display,
        "assignee_email": assignee_email,
        "parent_key": parent_key,
        "parent_summary": parent_summary,
        "parent_type": parent_type,
        "epic_link": epic_link,
        # Three states: True (reporter==assignee), False (reporter!=assignee),
        # None (indeterminate — assignee empty, can't compare)
        "self_created": None if not assignee else (reporter == assignee and reporter != ""),
        "labels": fields_data.get("labels", []),
        "priority": (fields_data.get("priority") or {}).get("name", ""),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


# ── Step 1: Extract ticket keys from GitHub PR data ────────────────────────

def extract_ticket_keys_from_prs():
    """
    Scan all PR data and extract JIRA ticket references from titles and branches.

    Returns:
        ticket_to_prs: dict mapping ticket_key -> list of PR info dicts
        all_prs_per_author: dict mapping author login -> total PR count
            (includes PRs with AND without ticket references)
    """
    ticket_to_prs = defaultdict(list)
    all_prs_per_author = defaultdict(int)

    if not DATA_DIR.exists():
        return ticket_to_prs, all_prs_per_author

    repo_dirs = sorted(
        d for d in DATA_DIR.iterdir()
        if d.is_dir()
        and d.name not in EXCLUDED_REPOS
        and not d.name.startswith("_")
    )

    for repo_dir in repo_dirs:
        prs_file = repo_dir / "prs.json"
        if not prs_file.exists():
            continue

        with open(prs_file) as f:
            prs = json.load(f)

        for pr in prs:
            title = pr.get("title", "")
            branch = pr.get("head_branch", "")
            author = pr.get("author", "")
            pr_number = pr.get("number", 0)
            repo_name = repo_dir.name

            # Count every PR toward the author's total, regardless of ticket
            if author and not is_bot(author):
                all_prs_per_author[author] += 1

            tickets_in_title = {f"{m[0]}-{m[1]}" for m in TICKET_PATTERN.findall(title)}
            tickets_in_branch = {f"{m[0]}-{m[1]}" for m in TICKET_PATTERN.findall(branch)}
            all_tickets = tickets_in_title | tickets_in_branch

            for ticket_key in all_tickets:
                ticket_to_prs[ticket_key].append({
                    "repo": repo_name,
                    "pr_number": pr_number,
                    "author": author,
                    "title": title,
                    "branch": branch,
                    "source": "title" if ticket_key in tickets_in_title else "branch",
                })

    return ticket_to_prs, all_prs_per_author


# ── Step 2: Fetch JIRA data ────────────────────────────────────────────────

ERROR_CACHE_TTL_HOURS = 24  # Auto-retry failed fetches after this many hours


def _is_stale_error(cache_path, retry_failed=False):
    """Check if a cache file is a failed-fetch error that should be retried."""
    try:
        with open(cache_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False
    if "error" not in data:
        return False
    if retry_failed:
        return True
    # Auto-retry errors older than TTL
    fetched_at = data.get("fetched_at", "")
    if fetched_at:
        try:
            fetch_time = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            now = datetime.now(fetch_time.tzinfo) if fetch_time.tzinfo else datetime.utcnow()
            age_hours = (now - fetch_time).total_seconds() / 3600
            if age_hours > ERROR_CACHE_TTL_HOURS:
                return True
        except (ValueError, TypeError):
            pass
    return False


def fetch_all_tickets(ticket_keys, headers, retry_failed=False):
    """
    Fetch all tickets from JIRA, with caching to avoid re-fetching.
    Uses a queue so that parent/epic tickets discovered during fetching
    are themselves fetched in the same run.

    Args:
        retry_failed: If True, re-fetch tickets that previously failed.
            Even without this flag, errors older than ERROR_CACHE_TTL_HOURS
            are automatically retried.
    """
    from collections import deque

    JIRA_TICKETS_DIR.mkdir(parents=True, exist_ok=True)

    # Build queue from initial keys, excluding already-cached
    seen = set(ticket_keys)
    queue = deque(sorted(ticket_keys))

    fetched = 0
    cached = 0
    failed = 0
    retried = 0
    processed = 0

    while queue:
        key = queue.popleft()
        processed += 1
        cache_path = JIRA_TICKETS_DIR / f"{key}.json"

        if cache_path.exists():
            # Check if this is a stale error that should be retried
            if _is_stale_error(cache_path, retry_failed):
                cache_path.unlink()
                retried += 1
                # Fall through to fetch below
            else:
                cached += 1
                _enqueue_ancestors(cache_path, seen, queue)
                continue

        print(f"  [{processed}/{processed + len(queue)}] Fetching {key}...", end="", flush=True)
        ticket_data = fetch_ticket(key, headers)

        if ticket_data:
            with open(cache_path, "w") as f:
                json.dump(ticket_data, f, indent=2)
            fetched += 1
            print(f" OK ({ticket_data['reporter_name']} -> {ticket_data['assignee_name']})")

            # Queue parent if not yet seen
            parent_key = ticket_data.get("parent_key")
            if parent_key and parent_key not in seen:
                if not (JIRA_TICKETS_DIR / f"{parent_key}.json").exists():
                    print(f"       -> queued parent {parent_key}")
                seen.add(parent_key)
                queue.append(parent_key)

            # Queue epic if not yet seen
            epic_link = ticket_data.get("epic_link")
            if epic_link and epic_link not in seen:
                if not (JIRA_TICKETS_DIR / f"{epic_link}.json").exists():
                    print(f"       -> queued epic {epic_link}")
                seen.add(epic_link)
                queue.append(epic_link)
        else:
            failed += 1
            print(" FAILED (not found or error)")
            with open(cache_path, "w") as f:
                json.dump({"key": key, "error": "fetch_failed", "fetched_at": datetime.utcnow().isoformat() + "Z"}, f)

    if retried:
        print(f"  Retried {retried} previously-failed tickets")

    return fetched, cached, failed


def _enqueue_ancestors(cache_path, seen, queue):
    """Check a cached ticket for parent/epic keys we haven't queued yet."""
    try:
        with open(cache_path) as f:
            data = json.load(f)
        if "error" in data:
            return
        for field in ("parent_key", "epic_link"):
            ancestor = data.get(field)
            if ancestor and ancestor not in seen:
                seen.add(ancestor)
                queue.append(ancestor)
    except (json.JSONDecodeError, IOError):
        pass


# ── Step 3: Build parent lineage and classify authority ─────────────────────

def load_ticket(key):
    """Load a cached ticket from disk."""
    path = JIRA_TICKETS_DIR / f"{key}.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    if "error" in data:
        return None
    return data


def build_lineage(ticket_key):
    """Walk up the parent chain. Returns list from leaf to root."""
    lineage = []
    visited = set()
    current_key = ticket_key
    depth = 0

    while current_key and depth < MAX_PARENT_DEPTH:
        if current_key in visited:
            break
        visited.add(current_key)

        ticket = load_ticket(current_key)
        if not ticket:
            break

        lineage.append(ticket)

        parent_key = ticket.get("parent_key")
        if not parent_key:
            parent_key = ticket.get("epic_link")

        current_key = parent_key
        depth += 1

    return lineage


def classify_authority(lineage, pr_author_name=None):
    """
    Classify a ticket's authority based on reporter/assignee heuristic
    applied across the full parent lineage.

    self_created values:
        False  — reporter != assignee (external authority confirmed)
        True   — reporter == assignee (self-created)
        None   — assignee empty (indeterminate)

    For non-root tickets (not Epic/Initiative) with self_created=None,
    the optional pr_author_name is used as the effective assignee:
    if reporter_name != pr_author_name → SANCTIONED.
    For root/epic tickets, indeterminate falls through to parents.

    Returns:
        authority_level: "SANCTIONED" | "INHERITED" | "UNSANCTIONED"
        authority_source: ticket key where authority was found (or None)
        authority_depth: how many levels up the chain authority was found
        details: human-readable explanation
    """
    if not lineage:
        return "UNKNOWN", None, -1, "No ticket data available"

    leaf = lineage[0]
    leaf_self_created = leaf.get("self_created")

    # For unassigned non-root tickets, fall back to PR author as effective assignee
    if leaf_self_created is None and pr_author_name:
        issue_type = (leaf.get("issue_type") or "").lower()
        if issue_type not in ("epic", "initiative"):
            reporter_name = leaf.get("reporter_name", "")
            if reporter_name:
                leaf_self_created = (reporter_name.lower() == pr_author_name.lower())

    # Check the leaf ticket: False means external authority confirmed
    if leaf_self_created is False:
        return (
            "SANCTIONED",
            leaf["key"],
            0,
            f"Reporter ({leaf['reporter_name']}) != Assignee ({leaf.get('assignee_name', 'unassigned')})"
            + (f" [effective assignee: {pr_author_name}]" if leaf.get("self_created") is None else "")
        )

    # Walk up the lineage: None (indeterminate) tickets are skipped,
    # True (self-created) tickets continue the search
    for depth, ancestor in enumerate(lineage[1:], start=1):
        if ancestor.get("self_created") is False:
            return (
                "INHERITED",
                ancestor["key"],
                depth,
                f"Authority inherited from {ancestor['key']} ({ancestor['issue_type']}): "
                f"Reporter ({ancestor['reporter_name']}) != Assignee ({ancestor['assignee_name']})"
            )

    ancestor_keys = " -> ".join(t["key"] for t in lineage)
    return (
        "UNSANCTIONED",
        None,
        -1,
        f"Self-created or indeterminate chain: {ancestor_keys}"
    )


# ── Step 4: Compute SWR per engineer ───────────────────────────────────────

def compute_swr(ticket_to_prs, all_prs_per_author):
    """
    Compute Sanctioned Work Ratio for each engineer.
    Links PRs -> tickets -> authority classification.

    The denominator (total_prs) is the TRUE total from all_prs_per_author,
    which includes PRs that have no JIRA ticket reference. The gap between
    the true total and the classified total is tracked as no_ticket_prs.
    """
    per_author = defaultdict(lambda: {
        "total_prs": 0,
        "sanctioned_prs": 0,
        "inherited_prs": 0,
        "unsanctioned_prs": 0,
        "unknown_prs": 0,
        "no_ticket_prs": 0,
        "classified_prs": 0,
        "tickets": defaultdict(lambda: {
            "authority": None,
            "pr_count": 0,
            "lineage": [],
        }),
    })

    # Set true totals from the full PR scan
    for author, total in all_prs_per_author.items():
        per_author[author]["total_prs"] = total

    # GitHub login -> display name mapping for PR-author-as-assignee fallback
    github_to_name = dict(TARGET_LOGINS) if TARGET_LOGINS else {}

    # Build lineages and base classifications (without PR author context)
    ticket_lineages = {}
    ticket_classifications = {}
    for ticket_key in ticket_to_prs:
        lineage = build_lineage(ticket_key)
        ticket_lineages[ticket_key] = lineage
        authority_level, authority_source, authority_depth, details = classify_authority(lineage)
        ticket_classifications[ticket_key] = {
            "authority_level": authority_level,
            "authority_source": authority_source,
            "authority_depth": authority_depth,
            "details": details,
            "lineage": [{"key": t["key"], "type": t["issue_type"],
                         "reporter": t["reporter_name"], "assignee": t["assignee_name"],
                         "self_created": t.get("self_created", True)}
                        for t in lineage],
        }

    def _needs_per_author_classification(ticket_key):
        """Check if ticket has an unassigned non-epic leaf that benefits from PR author fallback."""
        lineage = ticket_lineages.get(ticket_key, [])
        if not lineage:
            return False
        leaf = lineage[0]
        if leaf.get("self_created") is not None:
            return False  # Has assignee — base classification is final
        issue_type = (leaf.get("issue_type") or "").lower()
        return issue_type not in ("epic", "initiative")

    # A single PR may reference multiple tickets. To avoid double-counting,
    # collect the strongest authority level per (author, repo, pr_number) tuple,
    # then count each PR exactly once.
    AUTHORITY_PRIORITY = {"SANCTIONED": 3, "INHERITED": 2, "UNSANCTIONED": 1, "UNKNOWN": 0}

    # pr_key -> strongest_level
    pr_best_authority = {}

    for ticket_key, pr_list in ticket_to_prs.items():
        base_classification = ticket_classifications.get(ticket_key)
        if not base_classification:
            continue

        needs_per_author = _needs_per_author_classification(ticket_key)
        lineage = ticket_lineages.get(ticket_key, [])
        ticket_best_level = base_classification["authority_level"]

        for pr_info in pr_list:
            author = pr_info["author"]
            pr_key = (author, pr_info.get("repo", ""), pr_info.get("pr_number", 0))

            if needs_per_author and github_to_name:
                # Reclassify with PR author as effective assignee
                pr_author_name = github_to_name.get(author)
                level, _, _, details = classify_authority(lineage, pr_author_name=pr_author_name)
            else:
                level = base_classification["authority_level"]
                details = base_classification["details"]

            # Update the global ticket classification if this PR author provided a stronger authority
            if AUTHORITY_PRIORITY.get(level, 0) > AUTHORITY_PRIORITY.get(ticket_best_level, 0):
                ticket_best_level = level
                ticket_classifications[ticket_key]["authority_level"] = level
                ticket_classifications[ticket_key]["details"] = details

            prev_level = pr_best_authority.get(pr_key)
            if prev_level is None or AUTHORITY_PRIORITY.get(level, 0) > AUTHORITY_PRIORITY.get(prev_level, 0):
                pr_best_authority[pr_key] = level

            # Still record per-ticket detail (informational, not used for counts)
            per_author[author]["tickets"][ticket_key] = {
                "authority": level,
                "pr_count": per_author[author]["tickets"][ticket_key]["pr_count"] + 1,
                "lineage": base_classification["lineage"],
            }

    # Now count each PR exactly once using its strongest authority
    for (author, _repo, _pr_num), level in pr_best_authority.items():
        per_author[author]["classified_prs"] += 1
        if level == "SANCTIONED":
            per_author[author]["sanctioned_prs"] += 1
        elif level == "INHERITED":
            per_author[author]["inherited_prs"] += 1
        elif level == "UNSANCTIONED":
            per_author[author]["unsanctioned_prs"] += 1
        else:
            per_author[author]["unknown_prs"] += 1

    # Compute no_ticket_prs as the gap between true total and classified total
    for author, data in per_author.items():
        data["no_ticket_prs"] = max(0, data["total_prs"] - data["classified_prs"])

    return per_author, ticket_classifications


# ── Output & Reporting ──────────────────────────────────────────────────────

def print_swr_report(per_author, ticket_classifications):
    """Print SWR analysis. If TARGET_LOGINS is set, filters to those; otherwise shows all."""
    print()
    print("=" * 100)
    print("ENTROPY FRAMEWORK — SANCTIONED WORK RATIO (SWR) ANALYSIS")
    print("=" * 100)
    print()
    print("Heuristic: Reporter != Assignee -> SANCTIONED")
    print("           Reporter = Assignee, ancestor Reporter != Assignee -> INHERITED")
    print("           Reporter = Assignee, entire chain self-created -> UNSANCTIONED")
    print()

    header = (
        f"{'Author':<25} {'Total':>6} {'Sanct':>6} {'Inher':>6} {'Unsanc':>6} "
        f"{'NoTkt':>6} {'Unkn':>5} {'SWR':>7} {'SWR+I':>7}  {'Signal'}"
    )
    print(header)
    print("-" * 110)

    # Determine which authors to report on
    if TARGET_LOGINS:
        report_authors = TARGET_LOGINS
    else:
        # All authors with data, sorted by total PRs
        report_authors = {
            login: login for login in per_author
            if not is_bot(login)
        }

    results = []
    for login, display_name in report_authors.items():
        data = per_author.get(login, {
            "total_prs": 0, "sanctioned_prs": 0, "inherited_prs": 0,
            "unsanctioned_prs": 0, "unknown_prs": 0, "tickets": {},
        })

        total = data["total_prs"]
        sanctioned = data["sanctioned_prs"]
        inherited = data["inherited_prs"]
        unsanctioned = data["unsanctioned_prs"]
        no_ticket = data["no_ticket_prs"]
        unknown = data["unknown_prs"]

        # Denominator is TRUE total (includes PRs with no ticket reference)
        swr = sanctioned / total if total > 0 else 0.0
        swr_relaxed = (sanctioned + inherited) / total if total > 0 else 0.0

        if total == 0:
            signal = "NO DATA"
        elif swr_relaxed >= 0.8:
            signal = "DIRECTED"
        elif swr_relaxed >= 0.5:
            signal = "MIXED"
        else:
            signal = "SELF-DIRECTED"

        results.append({
            "login": login,
            "name": display_name,
            "total": total,
            "sanctioned": sanctioned,
            "inherited": inherited,
            "unsanctioned": unsanctioned,
            "no_ticket": no_ticket,
            "unknown": unknown,
            "swr": swr,
            "swr_relaxed": swr_relaxed,
            "signal": signal,
        })

    results.sort(key=lambda r: r["swr_relaxed"], reverse=True)

    for r in results:
        print(
            f"{r['name']:<25} {r['total']:>6} {r['sanctioned']:>6} {r['inherited']:>6} "
            f"{r['unsanctioned']:>6} {r['no_ticket']:>6} {r['unknown']:>5} "
            f"{r['swr']:>6.0%} {r['swr_relaxed']:>6.0%}  "
            f"{r['signal']}"
        )

    print()
    print("SWR  = Sanctioned PRs / Total PRs  (strict: only direct authority)")
    print("SWR+I = (Sanctioned + Inherited) / Total  (relaxed: parent authority counts)")
    print("Total includes PRs with no JIRA ticket reference (NoTkt column)")
    print()

    # Detail section: unsanctioned tickets
    print("=" * 100)
    print("UNSANCTIONED WORK DETAIL (self-created ticket chains)")
    print("=" * 100)

    for r in results:
        login = r["login"]
        data = per_author.get(login, {"tickets": {}})
        unsanctioned_tickets = {
            k: v for k, v in data.get("tickets", {}).items()
            if v.get("authority") == "UNSANCTIONED"
        }

        if not unsanctioned_tickets:
            continue

        print(f"\n  {r['name']} ({r['unsanctioned']} unsanctioned PRs across {len(unsanctioned_tickets)} tickets):")
        for ticket_key, ticket_info in sorted(unsanctioned_tickets.items()):
            lineage_str = " -> ".join(
                f"{t['key']}({t['reporter']})" for t in ticket_info.get("lineage", [])
            )
            ticket_data = load_ticket(ticket_key)
            summary = ticket_data.get("summary", "?") if ticket_data else "?"
            print(f"    {ticket_key}: {summary[:70]}")
            print(f"      Chain: {lineage_str}")

    return results


def save_swr_data(per_author, ticket_classifications, results):
    """Save full SWR analysis to JSON for downstream use."""
    JIRA_DIR.mkdir(parents=True, exist_ok=True)

    with open(JIRA_DIR / "ticket_classifications.json", "w") as f:
        json.dump(ticket_classifications, f, indent=2)

    serializable = {}
    for author, data in per_author.items():
        serializable[author] = {
            "total_prs": data["total_prs"],
            "sanctioned_prs": data["sanctioned_prs"],
            "inherited_prs": data["inherited_prs"],
            "unsanctioned_prs": data["unsanctioned_prs"],
            "no_ticket_prs": data["no_ticket_prs"],
            "unknown_prs": data["unknown_prs"],
            "tickets": {k: dict(v) for k, v in data["tickets"].items()},
        }
    with open(JIRA_DIR / "swr_per_author.json", "w") as f:
        json.dump(serializable, f, indent=2)

    with open(JIRA_DIR / "swr_analysis.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nData saved to {JIRA_DIR}/")
    print(f"  ticket_classifications.json  ({len(ticket_classifications)} tickets)")
    print(f"  swr_per_author.json          ({len(serializable)} authors)")
    print(f"  swr_analysis.json            ({len(results)} entries)")


# ── Main ────────────────────────────────────────────────────────────────────

def cmd_dry_run():
    """Show what would be fetched without making API calls."""
    print("Scanning GitHub PR data for JIRA ticket references...")
    ticket_to_prs, all_prs_per_author = extract_ticket_keys_from_prs()

    unique_tickets = set(ticket_to_prs.keys())
    projects = defaultdict(int)
    for key in unique_tickets:
        project = key.rsplit("-", 1)[0]
        projects[project] += 1

    # Count unique PRs (deduplicated — a PR referencing 2 tickets counts once)
    all_pr_keys = set()
    for ticket_key, pr_list in ticket_to_prs.items():
        for pr in pr_list:
            all_pr_keys.add((pr.get("author", ""), pr.get("repo", ""), pr.get("pr_number", 0)))

    print(f"\nFound {len(unique_tickets)} unique tickets linked from {len(all_pr_keys)} unique PRs")
    print(f"  ({sum(len(v) for v in ticket_to_prs.values())} ticket-PR associations before dedup)")
    print(f"\nProject distribution:")
    for project, count in sorted(projects.items(), key=lambda x: -x[1]):
        print(f"  {project}: {count} tickets")

    JIRA_TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    cached = sum(1 for k in unique_tickets if (JIRA_TICKETS_DIR / f"{k}.json").exists())
    print(f"\nAlready cached: {cached}")
    print(f"Need to fetch: {len(unique_tickets) - cached}")

    # Show per-author ticket coverage (deduplicated PR counts)
    author_stats = defaultdict(lambda: {"pr_keys": set(), "tickets": set()})
    for ticket_key, pr_list in ticket_to_prs.items():
        for pr in pr_list:
            author = pr["author"]
            if not is_bot(author):
                author_stats[author]["pr_keys"].add(
                    (pr.get("repo", ""), pr.get("pr_number", 0)))
                author_stats[author]["tickets"].add(ticket_key)

    report_authors = TARGET_LOGINS if TARGET_LOGINS else {a: a for a in author_stats}

    print(f"\nPer-author ticket coverage:")
    for login, name in sorted(report_authors.items()):
        stats = author_stats.get(login, {"pr_keys": set(), "tickets": set()})
        print(f"  {name:<25} {len(stats['pr_keys']):>4} PRs -> {len(stats['tickets']):>4} tickets")


def cmd_extract(retry_failed=False):
    """Extract JIRA ticket data for all tickets referenced in PRs."""
    headers = get_jira_auth()

    print("Scanning GitHub PR data for JIRA ticket references...")
    ticket_to_prs, _all_prs = extract_ticket_keys_from_prs()
    ticket_keys = set(ticket_to_prs.keys())
    print(f"Found {len(ticket_keys)} unique tickets")

    if retry_failed:
        print("  --retry-failed: will re-fetch previously failed tickets")

    print(f"\nFetching from JIRA (+ parent lineage)...")
    fetched, cached, failed = fetch_all_tickets(ticket_keys, headers, retry_failed=retry_failed)
    print(f"\nDone: {fetched} fetched, {cached} cached, {failed} failed")


def cmd_analyze():
    """Analyze SWR from cached JIRA data."""
    print("Scanning GitHub PR data for JIRA ticket references...")
    ticket_to_prs, all_prs_per_author = extract_ticket_keys_from_prs()
    print(f"Found {len(ticket_to_prs)} unique tickets across PRs")
    print(f"Total PRs across all authors: {sum(all_prs_per_author.values())}")

    cached = sum(1 for k in ticket_to_prs if (JIRA_TICKETS_DIR / f"{k}.json").exists())
    print(f"JIRA cache: {cached}/{len(ticket_to_prs)} tickets available")

    if cached == 0:
        print("\nNo JIRA data cached. Run 'extract' first.")
        return

    print("\nClassifying authority via parent lineage traversal...")
    per_author, ticket_classifications = compute_swr(ticket_to_prs, all_prs_per_author)

    results = print_swr_report(per_author, ticket_classifications)
    save_swr_data(per_author, ticket_classifications, results)


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_jira_swr.py [extract|analyze|all|dry-run] [--retry-failed]")
        print()
        print("Commands:")
        print("  dry-run        Show tickets and coverage without calling JIRA API")
        print("  extract        Fetch JIRA ticket data for all tickets referenced in PRs")
        print("  analyze        Compute SWR from cached JIRA data")
        print("  all            Run extract then analyze")
        print()
        print("Options:")
        print("  --retry-failed Re-fetch tickets that previously failed (transient errors)")
        print(f"                 (errors older than {ERROR_CACHE_TTL_HOURS}h are auto-retried regardless)")
        sys.exit(1)

    command = sys.argv[1].lower()
    retry_failed = "--retry-failed" in sys.argv[2:]

    if command == "dry-run":
        cmd_dry_run()
    elif command == "extract":
        cmd_extract(retry_failed=retry_failed)
    elif command == "analyze":
        cmd_analyze()
    elif command == "all":
        cmd_extract(retry_failed=retry_failed)
        cmd_analyze()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python extract_jira_swr.py [extract|analyze|all|dry-run] [--retry-failed]")
        sys.exit(1)


if __name__ == "__main__":
    main()
