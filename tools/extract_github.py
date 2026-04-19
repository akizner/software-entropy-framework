#!/usr/bin/env python3
"""
Entropy Framework — GitHub Data Extraction
===========================================
Pulls all repos from a GitHub org, commits with full diffs/patches,
PR metadata, and review data. Zero third-party dependencies.

UPSERT MODEL: never deletes existing data. New data is merged with
what's already on disk. Commits are keyed by SHA, PRs by number.
Safe to run repeatedly — only fetches what's missing.

Usage:
    export GITHUB_TOKEN=ghp_your_personal_access_token
    export GITHUB_ORG=your-org-name
    python extract_github.py

    # Extract only specific repos (comma-separated):
    python extract_github.py --repos repo1,repo2,repo3

    # Skip repos that already have a summary (fast re-run):
    python extract_github.py --skip-complete

Token permissions needed: repo (read), read:org
"""

import os
import sys
import json
import time
import argparse
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

# ============================================================================
# CONFIG
# ============================================================================

GITHUB_ORG = os.environ.get("GITHUB_ORG", "")
LOOKBACK_MONTHS = int(os.environ.get("LOOKBACK_MONTHS", "12"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path(__file__).parent.parent / "data")))

# Rate limit: GitHub allows 5,000/hour for authenticated users.
THROTTLE_SECONDS = 0.1

# Max diff size to store per commit (bytes). Set 0 for unlimited.
MAX_DIFF_SIZE_BYTES = 500_000  # 500KB per commit diff

# Commit batch file size
COMMIT_BATCH_SIZE = 200

# ============================================================================
# END CONFIG
# ============================================================================

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Headers are set lazily after credential validation in main()
HEADERS = {}
DIFF_HEADERS = {}

SINCE = (datetime.utcnow() - timedelta(days=LOOKBACK_MONTHS * 30)).isoformat() + "Z"

request_count = 0
rate_limit_remaining = 5000

# Regex to parse GitHub Link header for pagination
LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


# ============================================================================
# UPSERT HELPERS
# ============================================================================

def load_json(path, default=None):
    """Load JSON from disk, return default if missing or corrupt."""
    if not path.exists():
        return default if default is not None else []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default if default is not None else []


def save_json(path, data):
    """Write JSON to disk, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def upsert_commits(repo_output_dir, new_commits):
    """
    Merge new commits into existing batch files by SHA.
    Never deletes existing commits. New commits with same SHA
    are skipped (existing data wins).
    Returns: (total_count, new_count)
    """
    existing_by_sha = {}
    for batch_file in sorted(repo_output_dir.glob("commits_*.json")):
        batch = load_json(batch_file, [])
        for c in batch:
            existing_by_sha[c["sha"]] = c

    new_count = 0
    for c in new_commits:
        if c["sha"] not in existing_by_sha:
            existing_by_sha[c["sha"]] = c
            new_count += 1

    all_commits = sorted(
        existing_by_sha.values(),
        key=lambda c: c.get("date") or "",
        reverse=True,
    )

    for batch_idx in range(0, len(all_commits), COMMIT_BATCH_SIZE):
        batch = all_commits[batch_idx:batch_idx + COMMIT_BATCH_SIZE]
        batch_file = repo_output_dir / f"commits_{batch_idx:05d}.json"
        save_json(batch_file, batch)

    return len(all_commits), new_count


def upsert_commit_index(repo_output_dir, new_index_entries):
    """Merge new commit index entries by SHA. Existing entries preserved."""
    existing = load_json(repo_output_dir / "commit_index.json", [])
    existing_by_sha = {c["sha"]: c for c in existing}

    for entry in new_index_entries:
        if entry["sha"] not in existing_by_sha:
            existing_by_sha[entry["sha"]] = entry

    merged = sorted(
        existing_by_sha.values(),
        key=lambda c: c.get("date") or "",
        reverse=True,
    )
    save_json(repo_output_dir / "commit_index.json", merged)
    return len(merged)


def upsert_prs(repo_output_dir, new_prs):
    """
    Merge new PRs into existing file by PR number.
    Existing PRs are updated (newer data wins for PRs since
    reviews/comments may have been added).
    Returns: (total_count, new_count, updated_count)
    """
    existing = load_json(repo_output_dir / "prs.json", [])
    existing_by_number = {p["number"]: p for p in existing}

    new_count = 0
    updated_count = 0
    for p in new_prs:
        if p["number"] not in existing_by_number:
            existing_by_number[p["number"]] = p
            new_count += 1
        else:
            existing_by_number[p["number"]] = p
            updated_count += 1

    merged = sorted(
        existing_by_number.values(),
        key=lambda p: p.get("merged_at") or p.get("created_at") or "",
        reverse=True,
    )
    save_json(repo_output_dir / "prs.json", merged)
    return len(merged), new_count, updated_count


def upsert_summary(repo_output_dir, new_summary):
    """Merge summary: update counts, preserve old fields."""
    existing = load_json(repo_output_dir / "summary.json", {})
    if existing:
        existing.update(new_summary)
        for key in ("unique_commit_authors", "unique_pr_authors"):
            old_set = set(existing.get(key, []))
            new_set = set(new_summary.get(key, []))
            existing[key] = sorted(old_set | new_set)
        save_json(repo_output_dir / "summary.json", existing)
    else:
        save_json(repo_output_dir / "summary.json", new_summary)


def get_existing_commit_shas(repo_output_dir):
    """Fast check: which SHAs do we already have on disk?"""
    index = load_json(repo_output_dir / "commit_index.json", [])
    return set(c["sha"] for c in index)


# ============================================================================
# API HELPERS
# ============================================================================

def _build_url(base_url, params=None):
    """Append query params to a URL."""
    if not params:
        return base_url
    query = urllib.parse.urlencode(params)
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{query}"


def _parse_link_next(link_header):
    """Extract the 'next' URL from a GitHub Link header."""
    if not link_header:
        return None
    match = LINK_NEXT_RE.search(link_header)
    return match.group(1) if match else None


def api_get(url, params=None, headers=None, raw=False):
    """GET with rate limit handling and pagination support."""
    global request_count, rate_limit_remaining
    hdrs = headers or HEADERS

    results = []
    full_url = _build_url(url, params)

    while full_url:
        request_count += 1

        if rate_limit_remaining < 100:
            print(f"  Rate limit low ({rate_limit_remaining}). Pausing 60s...")
            time.sleep(60)
        elif THROTTLE_SECONDS:
            time.sleep(THROTTLE_SECONDS)

        req = urllib.request.Request(full_url, headers=hdrs, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))

                if request_count % 200 == 0:
                    print(f"  [{request_count} API calls | {rate_limit_remaining} remaining]")

                body = resp.read().decode("utf-8")

                if raw:
                    return body

                data = json.loads(body)
                if isinstance(data, list):
                    results.extend(data)
                else:
                    return data

                # Pagination
                link_header = resp.headers.get("Link", "")
                full_url = _parse_link_next(link_header)

        except urllib.error.HTTPError as e:
            status = e.code
            rate_limit_remaining = int(e.headers.get("X-RateLimit-Remaining", rate_limit_remaining))

            if status == 403:
                error_body = e.read().decode("utf-8", errors="replace")
                if "rate limit" in error_body.lower():
                    reset = int(e.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait = max(reset - int(time.time()), 1) + 10
                    print(f"  Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  WARNING: 403 for {full_url[:100]}")
                    return results if not raw else ""

            if status == 404:
                return [] if not raw else ""

            if status == 409:  # Empty repo
                return [] if not raw else ""

            print(f"  WARNING: {status} for {full_url[:100]}")
            return results if not raw else ""

        except Exception as e:
            print(f"  Network error: {e}. Retrying in 10s...")
            time.sleep(10)
            continue

    return results


def extract_git_trailers(message):
    """Parse SDLC and attribution trailers from commit message."""
    trailers = {}
    if not message:
        return trailers
    lines = message.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        if ": " in line and not line.startswith(" "):
            key, _, value = line.partition(": ")
            key = key.strip()
            if key.startswith(("SDLC-", "Generated-by", "Co-Authored-By", "Co-authored-by")):
                trailers[key] = value.strip()
        elif trailers:
            break
    return trailers


# ============================================================================
# DATA FETCHERS
# ============================================================================

def get_all_repos():
    """Fetch all repos in the org."""
    print(f"Fetching all repos for {GITHUB_ORG}...")
    repos = api_get(
        f"{GITHUB_API}/orgs/{GITHUB_ORG}/repos",
        params={"type": "all", "per_page": 100, "sort": "pushed", "direction": "desc"},
    )
    active = [r for r in repos if not r.get("archived") and r.get("size", 0) > 0]
    print(f"  Total repos: {len(repos)}, Active (non-archived, non-empty): {len(active)}")
    return active


def get_repo_commits(repo_name):
    """Fetch all commits in the lookback period."""
    return api_get(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/commits",
        params={"since": SINCE, "per_page": 100},
    )


def get_commit_detail(repo_name, sha):
    """Fetch single commit with file-level stats."""
    return api_get(f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/commits/{sha}")


def get_commit_diff(repo_name, sha):
    """Fetch the full unified diff for a commit."""
    diff = api_get(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/commits/{sha}",
        headers=DIFF_HEADERS,
        raw=True,
    )
    if diff and MAX_DIFF_SIZE_BYTES and len(diff) > MAX_DIFF_SIZE_BYTES:
        return f"[TRUNCATED — {len(diff)} bytes, limit {MAX_DIFF_SIZE_BYTES}]"
    return diff


def get_repo_merged_prs(repo_name):
    """Fetch merged PRs in the lookback period."""
    prs = api_get(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/pulls",
        params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 100},
    )
    return [p for p in prs if p.get("merged_at") and p["merged_at"] >= SINCE]


def get_pr_reviews(repo_name, pr_number):
    """Fetch review decisions."""
    reviews = api_get(f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/pulls/{pr_number}/reviews")
    return [
        {
            "author": r.get("user", {}).get("login"),
            "state": r.get("state"),
            "body": (r.get("body") or "")[:1000],
            "submitted_at": r.get("submitted_at"),
        }
        for r in reviews
    ]


def get_pr_review_comments(repo_name, pr_number):
    """Fetch inline review comments (the substantive ones)."""
    comments = api_get(f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo_name}/pulls/{pr_number}/comments")
    return [
        {
            "author": c.get("user", {}).get("login"),
            "body": (c.get("body") or "")[:2000],
            "path": c.get("path"),
            "created_at": c.get("created_at"),
        }
        for c in comments
    ]


# ============================================================================
# REPO EXTRACTION (with upsert)
# ============================================================================

def extract_repo(repo_info, repo_output_dir):
    """Extract all data for a single repo. Upserts into existing data."""
    repo_name = repo_info["name"]
    print(f"\n{'='*60}")
    print(f"Repo: {repo_name} (pushed: {repo_info.get('pushed_at', 'unknown')[:10]})")
    print(f"{'='*60}")

    pushed_at = repo_info.get("pushed_at", "")
    if pushed_at and pushed_at < SINCE:
        print(f"  Skipped — no pushes since {SINCE[:10]}")
        repo_output_dir.mkdir(parents=True, exist_ok=True)
        skip_file = repo_output_dir / "_skipped.json"
        if not skip_file.exists():
            save_json(skip_file, {"reason": "no_recent_pushes", "checked_at": datetime.utcnow().isoformat()})
        return

    repo_output_dir.mkdir(parents=True, exist_ok=True)

    existing_shas = get_existing_commit_shas(repo_output_dir)
    print(f"  Existing commits on disk: {len(existing_shas)}")

    # ---- COMMITS ----
    print(f"  Fetching commit list from GitHub...")
    raw_commits = get_repo_commits(repo_name)
    print(f"  Commits in period: {len(raw_commits)}")

    new_raw_commits = [rc for rc in raw_commits if rc["sha"] not in existing_shas]
    print(f"  New commits to fetch: {len(new_raw_commits)}")

    new_commits = []
    new_index_entries = []

    for i, rc in enumerate(new_raw_commits):
        sha = rc["sha"]
        commit_obj = rc.get("commit", {})
        message = commit_obj.get("message", "")
        author_login = rc.get("author", {}).get("login") if rc.get("author") else None
        author_name = commit_obj.get("author", {}).get("name")
        author_email = commit_obj.get("author", {}).get("email")
        date = commit_obj.get("author", {}).get("date")

        trailers = extract_git_trailers(message)

        if (i + 1) % 50 == 0:
            print(f"  Fetching diffs... [{i+1}/{len(new_raw_commits)}]")

        detail = get_commit_detail(repo_name, sha)
        diff = get_commit_diff(repo_name, sha)

        files = []
        if isinstance(detail, dict) and "files" in detail:
            files = [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "changes": f.get("changes", 0),
                    "patch": (f.get("patch") or "")[:50000],
                }
                for f in detail["files"]
            ]

        stats = {}
        if isinstance(detail, dict) and "stats" in detail:
            stats = detail["stats"]

        has_sdlc = any(k.startswith("SDLC-") for k in trailers)
        has_ai_gen = "Generated-by" in trailers

        commit_record = {
            "sha": sha,
            "author_login": author_login,
            "author_name": author_name,
            "author_email": author_email,
            "date": date,
            "message": message[:5000],
            "message_first_line": message.split("\n")[0][:300],
            "trailers": trailers,
            "has_sdlc_trailers": has_sdlc,
            "ai_generated": has_ai_gen,
            "stats": stats,
            "files": files,
            "diff": diff,
        }
        new_commits.append(commit_record)

        new_index_entries.append({
            "sha": sha,
            "author_login": author_login,
            "author_name": author_name,
            "date": date,
            "message_first_line": message.split("\n")[0][:300],
            "has_sdlc_trailers": has_sdlc,
            "ai_generated": has_ai_gen,
            "trailers": trailers,
            "additions": stats.get("additions", 0),
            "deletions": stats.get("deletions", 0),
            "total_changes": stats.get("total", 0),
            "file_count": len(files),
        })

    total_commits, added_commits = upsert_commits(repo_output_dir, new_commits)
    total_indexed = upsert_commit_index(repo_output_dir, new_index_entries)
    print(f"  Commits: {added_commits} new, {total_commits} total on disk")

    # ---- PULL REQUESTS ----
    print(f"  Fetching merged PRs...")
    raw_prs = get_repo_merged_prs(repo_name)
    print(f"  Merged PRs in period: {len(raw_prs)}")

    new_prs = []
    for j, rp in enumerate(raw_prs):
        pr_number = rp["number"]
        author = rp.get("user", {}).get("login")

        if (j + 1) % 20 == 0:
            print(f"  Fetching PR details... [{j+1}/{len(raw_prs)}]")

        reviews = get_pr_reviews(repo_name, pr_number)
        review_comments = get_pr_review_comments(repo_name, pr_number)

        created = datetime.fromisoformat(rp["created_at"].replace("Z", "+00:00"))
        merged = datetime.fromisoformat(rp["merged_at"].replace("Z", "+00:00"))
        cycle_time_hours = round((merged - created).total_seconds() / 3600, 2)

        new_prs.append({
            "number": pr_number,
            "title": rp["title"],
            "author": author,
            "created_at": rp["created_at"],
            "merged_at": rp["merged_at"],
            "base_branch": rp.get("base", {}).get("ref"),
            "head_branch": rp.get("head", {}).get("ref"),
            "additions": rp.get("additions", 0),
            "deletions": rp.get("deletions", 0),
            "changed_files": rp.get("changed_files", 0),
            "labels": [l["name"] for l in rp.get("labels", [])],
            "body": (rp.get("body") or "")[:3000],
            "cycle_time_hours": cycle_time_hours,
            "reviews": reviews,
            "review_comments": review_comments,
            "review_rounds": len([r for r in reviews if r["state"] in ("APPROVED", "CHANGES_REQUESTED")]),
            "changes_requested_count": len([r for r in reviews if r["state"] == "CHANGES_REQUESTED"]),
            "review_comment_count": len(review_comments),
        })

    total_prs, new_pr_count, updated_pr_count = upsert_prs(repo_output_dir, new_prs)
    print(f"  PRs: {new_pr_count} new, {updated_pr_count} updated, {total_prs} total on disk")

    # ---- REPO SUMMARY (upsert) ----
    full_index = load_json(repo_output_dir / "commit_index.json", [])
    full_prs = load_json(repo_output_dir / "prs.json", [])

    summary = {
        "repo": repo_name,
        "default_branch": repo_info.get("default_branch"),
        "language": repo_info.get("language"),
        "size_kb": repo_info.get("size"),
        "pushed_at": repo_info.get("pushed_at"),
        "period_start": SINCE[:10],
        "period_end": datetime.utcnow().isoformat()[:10],
        "last_extraction": datetime.utcnow().isoformat(),
        "total_commits": len(full_index),
        "total_merged_prs": len(full_prs),
        "unique_commit_authors": sorted(set(c["author_login"] for c in full_index if c.get("author_login"))),
        "unique_pr_authors": sorted(set(p["author"] for p in full_prs if p.get("author"))),
        "sdlc_commits": len([c for c in full_index if c.get("has_sdlc_trailers")]),
        "ai_generated_commits": len([c for c in full_index if c.get("ai_generated")]),
    }

    upsert_summary(repo_output_dir, summary)

    print(f"  Done: {len(full_index)} commits, {len(full_prs)} PRs on disk")
    return summary


# ============================================================================
# MAIN
# ============================================================================

def main():
    global TOKEN, HEADERS, DIFF_HEADERS, GITHUB_ORG

    parser = argparse.ArgumentParser(description="Entropy Framework — GitHub data extraction (upsert mode)")
    parser.add_argument("--repos", type=str, help="Comma-separated repo names (default: all in org)")
    parser.add_argument("--skip-complete", action="store_true",
                        help="Skip repos that already have a summary.json (fast re-run for new repos only)")
    args = parser.parse_args()

    # Validate credentials after argparse so --help works without env vars
    if not TOKEN:
        print("ERROR: Set GITHUB_TOKEN environment variable")
        print("  export GITHUB_TOKEN=ghp_your_personal_access_token")
        sys.exit(1)

    if not GITHUB_ORG:
        print("ERROR: Set GITHUB_ORG environment variable")
        print("  export GITHUB_ORG=your-org-name")
        sys.exit(1)

    HEADERS.update({
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    DIFF_HEADERS.update({
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
    })

    print(f"Entropy Framework — GitHub Data Extraction (upsert mode)")
    print(f"Org: {GITHUB_ORG}")
    print(f"Lookback: {LOOKBACK_MONTHS} months (since {SINCE[:10]})")
    print(f"Output: {OUTPUT_DIR.resolve()}")
    print(f"Mode: upsert (existing data is never deleted)")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.repos:
        repo_names = [r.strip() for r in args.repos.split(",")]
        all_repos = [{
            "name": r, "archived": False, "size": 1,
            "pushed_at": SINCE, "default_branch": "master", "language": "unknown",
        } for r in repo_names]
        print(f"Extracting {len(all_repos)} specified repos")
    else:
        all_repos = get_all_repos()

    # Upsert repo list
    repo_list_file = OUTPUT_DIR / "_repos.json"
    existing_repos = {r["name"]: r for r in load_json(repo_list_file, [])}
    for r in all_repos:
        existing_repos[r["name"]] = {
            "name": r["name"],
            "language": r.get("language"),
            "size_kb": r.get("size"),
            "pushed_at": r.get("pushed_at"),
        }
    save_json(repo_list_file, sorted(existing_repos.values(), key=lambda r: r["name"]))

    summaries = []
    skipped = 0
    errors = []

    for idx, repo_info in enumerate(all_repos):
        repo_name = repo_info["name"]
        repo_output_dir = OUTPUT_DIR / repo_name

        if args.skip_complete and (repo_output_dir / "summary.json").exists():
            skipped += 1
            summaries.append(load_json(repo_output_dir / "summary.json", {}))
            continue

        print(f"\n[{idx+1}/{len(all_repos)}] ", end="")

        try:
            summary = extract_repo(repo_info, repo_output_dir)
            if summary:
                summaries.append(summary)
        except Exception as e:
            print(f"  ERROR extracting {repo_name}: {e}")
            errors.append({"repo": repo_name, "error": str(e), "at": datetime.utcnow().isoformat()})
            repo_output_dir.mkdir(parents=True, exist_ok=True)
            error_log = load_json(repo_output_dir / "_errors.json", [])
            error_log.append({"error": str(e), "at": datetime.utcnow().isoformat()})
            save_json(repo_output_dir / "_errors.json", error_log)

    if skipped:
        print(f"\nSkipped {skipped} already-complete repos (--skip-complete)")

    # ---- ORG-WIDE SUMMARY ----
    print(f"\n{'='*60}")
    print("ORG-WIDE EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total API calls: {request_count}")
    print(f"Repos processed: {len(summaries)}")
    if skipped:
        print(f"Repos skipped: {skipped}")
    if errors:
        print(f"Repos with errors: {len(errors)}")

    total_commits = sum(s.get("total_commits", 0) for s in summaries)
    total_prs = sum(s.get("total_merged_prs", 0) for s in summaries)
    sdlc_commits = sum(s.get("sdlc_commits", 0) for s in summaries)
    ai_commits = sum(s.get("ai_generated_commits", 0) for s in summaries)

    all_authors = set()
    for s in summaries:
        all_authors.update(s.get("unique_commit_authors", []))

    print(f"\nTotal commits on disk: {total_commits}")
    print(f"Total merged PRs on disk: {total_prs}")
    print(f"Unique authors: {len(all_authors)}")
    print(f"SDLC-attributed commits: {sdlc_commits} ({sdlc_commits/max(total_commits,1)*100:.1f}%)")
    print(f"AI-generated commits: {ai_commits} ({ai_commits/max(total_commits,1)*100:.1f}%)")

    author_counts = Counter()
    for s in summaries:
        for author in s.get("unique_commit_authors", []):
            author_counts[author] += 1

    print(f"\nTop 20 most active authors (by repos touched):")
    for author, count in author_counts.most_common(20):
        print(f"  {author}: {count} repos")

    # Upsert org summary
    org_summary_file = OUTPUT_DIR / "_org_summary.json"
    existing_org = load_json(org_summary_file, {})

    org_summary = {
        "org": GITHUB_ORG,
        "last_extraction": datetime.utcnow().isoformat(),
        "period_start": SINCE[:10],
        "period_end": datetime.utcnow().isoformat()[:10],
        "total_repos_in_org": len(all_repos),
        "repos_with_data": len(summaries),
        "total_commits": total_commits,
        "total_merged_prs": total_prs,
        "unique_authors": sorted(all_authors),
        "sdlc_commits": sdlc_commits,
        "ai_generated_commits": ai_commits,
        "repo_summaries": summaries,
    }

    all_errors = existing_org.get("error_history", [])
    if errors:
        all_errors.append({
            "run": datetime.utcnow().isoformat(),
            "errors": errors,
        })
    org_summary["error_history"] = all_errors

    save_json(org_summary_file, org_summary)

    print(f"\nData saved to: {OUTPUT_DIR.resolve()}")
    print(f"Org summary: {org_summary_file}")
    print(f"\nNext step: run the analysis script on this data.")
    if errors:
        print(f"\nTo retry failed repos:")
        print(f"  python extract_github.py --repos {','.join(e['repo'] for e in errors)}")


if __name__ == "__main__":
    main()
