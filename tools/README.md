# Entropy Framework — Measurement Tools

> Extract, classify, and analyze engineering organization health from artifact data.

---

## Philosophy

These tools measure exhaust, not testimony. They read Git history, PR reviews, and issue tracker data — artifacts produced as natural byproducts of work. No surveys, no self-reporting, no instrumentation burden on developers.

The data is already honest. These tools just read it.

## Prerequisites

No third-party dependencies. All tools use Python 3's standard library (`urllib.request`, `json`, `argparse`).

You need:
- A GitHub personal access token with `repo` and `read:org` permissions
- (Optional) A JIRA API token for Sanctioned Work Ratio analysis

## Configuration

All tools read from environment variables:

```bash
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_ORG=your-org-name

# For JIRA integration (optional):
export JIRA_URL=https://your-org.atlassian.net
export JIRA_EMAIL=your-email@company.com
export JIRA_API_TOKEN=your_jira_api_token

# For project filtering (optional, comma-separated):
export JIRA_PROJECTS=PROJ1,PROJ2

# For filtering to specific users and mapping GitHub logins to Jira Display Names:
# Format MUST be "github_login:Jira Display Name" for correct unassigned-ticket fallback.
export TARGET_LOGINS="jdoe:Jane Doe,asmith:Alex Smith"

# JIRA custom field IDs (vary by instance — check your JIRA admin):
export JIRA_FIELD_EPIC_LINK=customfield_10014     # default
export JIRA_FIELD_STORY_POINTS=customfield_10008   # default
```

## Tools

### extract_github.py — GitHub Data Extraction

Pulls all repos from the org, commits with diffs, PR metadata, and review data. Uses an upsert model — safe to run repeatedly, only fetches what's missing.

```bash
python tools/extract_github.py

# Extract specific repos only:
python tools/extract_github.py --repos repo1,repo2,repo3

# Skip repos that already have data:
python tools/extract_github.py --skip-complete
```

Outputs to `data/` directory: per-repo JSON files with commits, PRs, reviews, and summary statistics.

### extract_jira_swr.py — Sanctioned Work Ratio Analysis

Extracts JIRA tickets linked to GitHub PRs and classifies them by authority chain:

- **SANCTIONED**: ticket created by external authority (PM, architect)
- **INHERITED**: ticket created by assignee, but parent chain has external authority
- **UNSANCTIONED**: entire parent chain is self-created

```bash
# Dry run — show tickets and coverage without calling JIRA API:
python tools/extract_jira_swr.py dry-run

# Extract tickets:
python tools/extract_jira_swr.py extract

# Analyze SWR per engineer:
python tools/extract_jira_swr.py analyze

# Full pipeline:
python tools/extract_jira_swr.py all
```

### analyze_archetypes.py — Developer Archetype Classification

Reads extracted GitHub data and classifies developers into archetypes based on the two-axis formula (Production Signal vs Catalyst Signal):

```bash
python tools/analyze_archetypes.py

# Filter to specific people:
TARGET_LOGINS="jdoe:Jane Doe,asmith:Alex Smith" python tools/analyze_archetypes.py

# Export to CSV:
python tools/analyze_archetypes.py --format csv > archetypes.csv
```

## What's Implemented vs Framework-Defined

The bundled tools compute: **PS, CS** (without cross-boundary multiplier), **CD, CRR, SWR** (with authority lineage depth), and **archetype classification**.

The following metrics are defined in the framework documents but do **not** have reference implementations bundled:

- **ACD (Authority Chain Depth)** — the bundled SWR tool emits `authority_depth` (how far up the parent chain authority was found), but does not classify reporter roles (PM, architect, etc.) as the full ACD definition requires
- **Cross-boundary multiplier for CS** — requires a repo-to-team ownership mapping CSV
- **Amplification Ratio** — requires monthly extraction runs and time-series comparison
- **Completion Ratio** — requires code-path overlap detection across PRs
- **Foreign Technology Ratio (FTR)** — requires a standard-stack definition file
- **Intelligence Quotient (IQ)** — requires token instrumentation not available from Git/JIRA

The raw data needed for most of these is present in the extracted output. See the Extending section below.

## Output Structure

```
data/
+-- {repo-name}/
|   +-- commits_00000.json   # Commit history with diffs (batched)
|   +-- commit_index.json    # Lightweight commit index
|   +-- prs.json             # PR metadata with reviews and comments
|   +-- summary.json         # Aggregated stats
+-- _jira/
|   +-- tickets/             # Cached JIRA tickets
|   +-- swr_analysis.json   # SWR classification results
+-- _org_summary.json        # Org-wide aggregation
+-- _archetypes.json         # Developer archetype classifications
```

## Data Privacy

These tools extract data from your organization's existing systems. The output contains developer names, commit history, and review content. Handle accordingly:

- Store output in a private location
- Do not commit extracted data to public repositories
- Review data before sharing outside your organization
- The framework measures artifacts, not people — but the data contains both

## Extending

The tools are designed to be modified. Common extensions:

- **Ownership mapping**: Add a CSV mapping repos to teams for cross-boundary review detection
- **LLM classification**: Pipe review comments through an LLM to classify as architectural/structural/correctness/cosmetic
- **Time-series**: Run extraction monthly and compare metrics over time for Amplification Ratio calculation
- **Slack integration**: Add Slack API extraction for knowledge diffusion signals (referenced in the framework as a future data source, not currently instrumented)
