#!/usr/bin/env python3
"""
Entropy Framework — Developer Archetype Classification
======================================================
Reads extracted GitHub data and classifies developers into archetypes
based on the two-axis formula (Production Signal vs Catalyst Signal).

Computes per-developer:
  PS  = Commits x Repos Committed
  CS  = Reviews x Repos Reviewed
  CD  = Inline Comments / Reviews
  CRR = Change Requests / Reviews

Then classifies into archetypes:
  System Governor, Selective Catalyst, Hybrid Producer+Catalystalyst,
  Production Engine, High-Entropy Agent, Fresh-Eyes Catalyst,
  Depleting Catalyst, Pure Reviewer, Rubber Stamp, Absent

Configuration (environment variables):
  OUTPUT_DIR       — path to extracted data (default: ./data)
  EXCLUDED_REPOS   — comma-separated repos to skip (e.g., infra, config repos)
  TARGET_LOGINS    — comma-separated login:Name pairs to filter to
                     (e.g., "jdoe:Jane Doe,asmith:Alex Smith")
                     If not set, analyzes all authors found in the data.

Usage:
    python analyze_archetypes.py

    # Filter to specific team:
    TARGET_LOGINS="jdoe:Jane Doe,asmith:Alex Smith" python analyze_archetypes.py

    # Export to CSV:
    python analyze_archetypes.py --format csv > archetypes.csv
"""

import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path(__file__).parent.parent / "data")))

# Optional: repos to exclude (comma-separated env var)
_excluded_env = os.environ.get("EXCLUDED_REPOS", "")
EXCLUDED_REPOS = set(r.strip() for r in _excluded_env.split(",") if r.strip()) if _excluded_env else set()

# Optional: filter to specific GitHub logins
_target_env = os.environ.get("TARGET_LOGINS", "")
TARGET_LOGINS = {}
if _target_env:
    for entry in _target_env.split(","):
        entry = entry.strip()
        if ":" in entry:
            login, name = entry.split(":", 1)
            TARGET_LOGINS[login.strip()] = name.strip()
        elif entry:
            TARGET_LOGINS[entry] = entry

BOT_SUFFIXES = ("[bot]",)


def is_bot(login):
    if not login:
        return True
    return any(login.endswith(s) for s in BOT_SUFFIXES)


def load_json(path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


# ── Archetype Classification ───────────────────────────────────────────────

def classify_archetype(ps, cs, cd, crr, commits, reviews):
    """
    Classify a developer into an archetype based on their signals.

    Thresholds are relative — calibrate to your org's median values.
    These defaults assume a 12-month lookback for a mid-size org.
    """
    if commits == 0 and reviews == 0:
        return "Absent"

    if reviews > 0 and cd == 0:
        return "Rubber Stamp"

    # High on both axes
    if ps > 500 and cs > 500:
        if cd > 0.7:
            return "System Governor" if cs > ps else "Hybrid Producer+Catalystalyst"
        else:
            return "High-Entropy Agent"

    # High catalyst, low production
    if cs > 200 and ps < 200:
        if commits < 10:
            if cd > 0.7:
                return "Depleting Catalyst"
            else:
                return "Pure Reviewer"
        if cd > 0.4:
            return "Selective Catalyst"
        return "Pure Reviewer"

    # High production, low catalyst
    if ps > 200 and cs < 200:
        return "Production Engine"

    # Moderate both
    if ps > 50 and cs > 50:
        if cd > 0.4:
            return "Hybrid Producer+Catalystalyst"
        return "High-Entropy Agent"

    # Low everything but present
    if reviews > 0 and cd > 0.4:
        return "Fresh-Eyes Catalyst"

    if commits > 0:
        return "Production Engine"

    return "Absent"


# ── Main Analysis ──────────────────────────────────────────────────────────

def analyze(output_format="table"):
    per_person = defaultdict(lambda: {
        "commits": 0,
        "repos_committed": set(),
        "reviews": 0,
        "repos_reviewed": set(),
        "inline_comments": 0,
        "changes_requested": 0,
        "loc_added": 0,
        "loc_deleted": 0,
    })

    if not DATA_DIR.exists():
        print(f"ERROR: Data directory does not exist: {DATA_DIR}")
        print(f"Run extract_github.py first to extract data.")
        return []

    repo_dirs = sorted(d for d in DATA_DIR.iterdir()
                       if d.is_dir() and d.name not in EXCLUDED_REPOS
                       and not d.name.startswith("_"))

    included_repos = 0

    for repo_dir in repo_dirs:
        skip_file = repo_dir / "_skipped.json"
        if skip_file.exists():
            continue

        commit_index = load_json(repo_dir / "commit_index.json")
        prs = load_json(repo_dir / "prs.json")

        if not commit_index and not prs:
            continue

        included_repos += 1
        repo_name = repo_dir.name

        for c in commit_index:
            login = c.get("author_login")
            if login and not is_bot(login):
                per_person[login]["commits"] += 1
                per_person[login]["repos_committed"].add(repo_name)
                per_person[login]["loc_added"] += c.get("additions", 0)
                per_person[login]["loc_deleted"] += c.get("deletions", 0)

        for pr in prs:
            # Deduplicate reviews: one review per reviewer per PR,
            # taking the strongest state. Excludes DISMISSED per metrics.md.
            # State priority: CHANGES_REQUESTED > APPROVED > COMMENTED
            STATE_PRIORITY = {"CHANGES_REQUESTED": 3, "APPROVED": 2, "COMMENTED": 1}
            reviewer_best = {}  # reviewer -> strongest state
            for review in pr.get("reviews", []):
                reviewer = review.get("author")
                if is_bot(reviewer):
                    continue
                state = review.get("state", "")
                if state not in STATE_PRIORITY:
                    continue  # skip DISMISSED, PENDING, etc.
                prev = reviewer_best.get(reviewer)
                if prev is None or STATE_PRIORITY[state] > STATE_PRIORITY.get(prev, 0):
                    reviewer_best[reviewer] = state

            for reviewer, state in reviewer_best.items():
                per_person[reviewer]["reviews"] += 1
                per_person[reviewer]["repos_reviewed"].add(repo_name)
                if state == "CHANGES_REQUESTED":
                    per_person[reviewer]["changes_requested"] += 1

            for comment in pr.get("review_comments", []):
                commenter = comment.get("author")
                if not is_bot(commenter):
                    per_person[commenter]["inline_comments"] += 1

    # Filter to target logins if specified
    if TARGET_LOGINS:
        report_logins = set(TARGET_LOGINS.keys())
    else:
        report_logins = set(per_person.keys())

    # Compute signals and classify
    results = []
    for login in report_logins:
        d = per_person.get(login, {
            "commits": 0, "repos_committed": set(), "reviews": 0,
            "repos_reviewed": set(), "inline_comments": 0,
            "changes_requested": 0, "loc_added": 0, "loc_deleted": 0,
        })

        display_name = TARGET_LOGINS.get(login, login)
        commits = d["commits"]
        repos_c = len(d["repos_committed"]) if isinstance(d["repos_committed"], set) else d["repos_committed"]
        reviews = d["reviews"]
        repos_r = len(d["repos_reviewed"]) if isinstance(d["repos_reviewed"], set) else d["repos_reviewed"]
        inline = d["inline_comments"]
        cr = d["changes_requested"]

        ps = commits * repos_c
        cs = reviews * repos_r
        cd = round(inline / reviews, 2) if reviews > 0 else 0.0
        crr = round(cr / reviews, 2) if reviews > 0 else 0.0

        archetype = classify_archetype(ps, cs, cd, crr, commits, reviews)

        results.append({
            "login": login,
            "name": display_name,
            "archetype": archetype,
            "ps": ps,
            "cs": cs,
            "cd": cd,
            "crr": crr,
            "commits": commits,
            "repos_committed": repos_c,
            "reviews": reviews,
            "repos_reviewed": repos_r,
            "inline_comments": inline,
            "changes_requested": cr,
            "loc_added": d["loc_added"],
            "loc_deleted": d["loc_deleted"],
        })

    results.sort(key=lambda r: r["cs"], reverse=True)

    # ── Output ──

    if output_format == "csv":
        print("login,name,archetype,PS,CS,CD,CRR,commits,repos_committed,"
              "reviews,repos_reviewed,inline_comments,changes_requested,loc_added,loc_deleted")
        for r in results:
            print(f"{r['login']},{r['name']},{r['archetype']},{r['ps']},{r['cs']},"
                  f"{r['cd']},{r['crr']},{r['commits']},{r['repos_committed']},"
                  f"{r['reviews']},{r['repos_reviewed']},{r['inline_comments']},"
                  f"{r['changes_requested']},{r['loc_added']},{r['loc_deleted']}")
        return results

    if output_format == "json":
        print(json.dumps(results, indent=2))
        return results

    # Default: table
    print("=" * 140)
    print("ENTROPY FRAMEWORK — DEVELOPER ARCHETYPE CLASSIFICATION")
    print("=" * 140)
    print(f"Repos analyzed: {included_repos}")
    if EXCLUDED_REPOS:
        print(f"Repos excluded: {', '.join(sorted(EXCLUDED_REPOS))}")
    print()

    print(f"{'Name':<25} {'Archetype':<25} {'PS':>8} {'CS':>8} {'CD':>5} {'CRR':>5}  "
          f"{'Commits':>7} {'Repos_C':>7} {'Reviews':>7} {'Repos_R':>7} {'Inline':>7} {'LOC+':>9} {'LOC-':>9}")
    print("-" * 140)

    for r in results:
        cd_indicator = "G" if r["cd"] > 0.7 else ("Y" if r["cd"] >= 0.4 else "R")
        print(f"{r['name']:<25} {r['archetype']:<25} {r['ps']:>8,} {r['cs']:>8,} "
              f"{r['cd']:>4.2f}{cd_indicator} {r['crr']:>5.2f}  "
              f"{r['commits']:>7,} {r['repos_committed']:>7} {r['reviews']:>7,} {r['repos_reviewed']:>7} "
              f"{r['inline_comments']:>7,} {r['loc_added']:>9,} {r['loc_deleted']:>9,}")

    print()
    print("=" * 140)
    print("FORMULA REFERENCE")
    print("  PS  = Commits x Repos Committed          (Production Signal)")
    print("  CS  = Reviews x Repos Reviewed            (Catalyst Signal)")
    print("  CD  = Inline Comments / Reviews           (Catalyst Density: G >0.7 | Y 0.4-0.7 | R <0.4)")
    print("  CRR = Change Requests / Reviews           (Change Request Rate)")
    print()
    print("ARCHETYPES")
    print("  System Governor       — high PS, high CS, high CD (rare)")
    print("  Selective Catalyst    — low PS, high CS, moderate+ CD")
    print("  Hybrid Producer+Catalyst  — high PS, high CS, balanced")
    print("  Production Engine     — high PS, low CS")
    print("  High-Entropy Agent    — high PS, mid CS, low CD")
    print("  Fresh-Eyes Catalyst   — low PS, growing reviews, moderate CD")
    print("  Depleting Catalyst    — low PS, mid CS, high CD (production stopped)")
    print("  Pure Reviewer         — very low PS, reviews without substance")
    print("  Rubber Stamp          — reviews with zero inline depth")
    print("  Absent                — no measurable signal")
    print("=" * 140)

    # Save to JSON
    output_file = DATA_DIR / "_archetypes.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Entropy Framework — Developer Archetype Classification")
    parser.add_argument("--format", choices=["table", "csv", "json"], default="table",
                        help="Output format (default: table)")
    args = parser.parse_args()

    analyze(output_format=args.format)


if __name__ == "__main__":
    main()
