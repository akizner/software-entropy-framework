# Entropy Framework — Metrics Reference

> v2 | Two-Axis Formula | April 2026

---

## Raw Metrics (extracted from GitHub)

| Metric | Source | Description |
|---|---|---|
| **Commits** | `git log --author` | Total commits authored across all repos |
| **Repos Committed** | derived | Unique repos the person committed to |
| **LOC (Lines of Code) Add / Del** | commit diffs | Lines of code added and deleted |
| **PRs (Pull Requests)** | GitHub API | Pull requests authored |
| **Reviews** | GitHub API (reviews array) | PRs reviewed (APPROVED, CHANGES_REQUESTED, or COMMENTED states). Deduplicated: one review per reviewer per PR, taking the strongest state. DISMISSED reviews are excluded. |
| **Inline** | GitHub API (review_comments) | Inline code comments left during reviews — comments attached to specific lines of code, not general PR comments |
| **CR (Change Requests)** | GitHub API (reviews with state=CHANGES_REQUESTED) | Reviews where the reviewer formally requested changes. Measures pushback |
| **Repos Reviewed** | derived | Unique repos where the person reviewed PRs |
| **Cross-Boundary** | derived from ownership mapping | Reviews on repos not owned by the reviewer's own team. Measures reach beyond home territory |

---

## Computed Signals

### Production Signal (PS)

```
PS = Commits x Repos Committed
```

Absolute production volume weighted by breadth. A person with 100 commits in 1 repo (PS=100) produces differently than 100 commits across 10 repos (PS=1000). No upper bound, no normalization.

### Catalyst Signal (CS)

```
CS = Reviews x Repos Reviewed x (1 + Cross-Boundary Ratio)
```

Where `Cross-Boundary Ratio = Cross-Boundary Reviews / Total Reviews`

Absolute catalyst volume weighted by breadth and amplified by cross-team reach. The cross-boundary multiplier ranges from 1.0 (all reviews inside own team) to 2.0 (all reviews outside own team). A review that crosses team boundaries carries more organizational weight.

> **Implementation note:** The cross-boundary multiplier requires a repo-to-team ownership mapping not bundled with the reference tools. Without it, `analyze_archetypes.py` computes `CS = Reviews x Repos Reviewed` (multiplier omitted). See the Extending section in `tools/README.md` for how to add ownership mapping.

### Catalyst Density (CD)

```
CD = Inline Comments / Reviews
```

Depth per review. How many inline code comments does the reviewer leave per review on average.

- **CD > 0.7** = substantive (green) — meaningful engagement with the code
- **CD 0.4-0.7** = moderate (yellow) — some depth
- **CD < 0.4** = shallow (red) — rubber-stamp territory

A CD above 1.0 means more inline comments than reviews — every review gets multiple detailed comments.

### Change Request Rate (CRR)

```
CRR = Change Requests / Reviews
```

Pushback rate. What fraction of reviews result in a formal "changes requested" verdict rather than approval.

- **CRR = 0** — never pushes back (could indicate rubber-stamping or team with high code quality)
- **CRR > 0** — exercises judgment to reject, not just approve

---

## Why Two Axes, Not One

The original formula was:

```
Catalyst Index (deprecated) = (Reviews x Repos Reviewed) / Commits
```

**Problem**: This punishes people who do both. A team leader working 100 hours producing AND reviewing gets a lower index than someone who only reviews. The formula rewarded one-dimensional behavior.

**Solution**: Decouple into two independent axes. PS and CS are never divided by each other. High on both = most valuable. High on one = specialized role. The framework measures what you do, not what you don't.

---

## Archetype Quick Reference

| Archetype | PS | CS | CD | Signal |
|---|---|---|---|---|
| **System Governor** | high | high | high | Dominates both axes — rare |
| **Selective Catalyst** | low | high | moderate | Strong catalyst within domain boundary |
| **Hybrid Producer+Catalyst** | high | high | high | Strong on both, balanced |
| **Production Engine** | high | low | — | Builds, doesn't review much |
| **High-Entropy Agent** | high | mid | low | Produces a lot, reviews shallowly, expensive AI spend |
| **Fresh-Eyes Catalyst** | low | mid | moderate | Low production, growing review presence |
| **Depleting Catalyst** | low | mid | high | Deep reviews but production nearly stopped |
| **Pure Reviewer** | very low | low | low | Reviews exist but with zero substance |
| **Rubber Stamp** | low | low | zero | Reviews exist but with zero depth |
| **Absent** | zero | zero | zero | No measurable signal |

---

## Intelligence Measurement Layer

### Sanctioned Work Ratio (SWR)

```
SWR = Sanctioned PRs / Total PRs
```

Fraction of an engineer's output that traces to tickets created by external authority (product manager, architect, or technical leadership) rather than self-created tickets.

**Heuristic:**
- Reporter != Assignee (both present) -> **SANCTIONED** (someone else requested this work)
- Assignee empty, non-root ticket (Story/Task/Bug) -> **PR author fallback**: compare Reporter name against the PR author's display name (resolved via `TARGET_LOGINS` mapping). If different -> SANCTIONED. If same -> self-created. If no mapping available -> indeterminate, falls through to parent lineage.
- Assignee empty, root ticket (Epic/Initiative) -> **indeterminate** at this level; falls through to parent lineage check. Epics are planning containers — the assignee field is not a "who did the work" signal.
- Reporter = Assignee, but ancestor Reporter != Assignee -> **INHERITED** (authority flows from parent epic/story)
- Reporter = Assignee (or indeterminate), entire parent chain has no external authority -> **UNSANCTIONED**

**Variants:**
- **SWR (strict)** = Sanctioned / Total — only direct authority counts
- **SWR+I (relaxed)** = (Sanctioned + Inherited) / Total — parent authority counts

### Authority Chain Depth (ACD)

```
ACD = number of approval layers above ticket creation
```

- **ACD-0**: self-created, self-approved — zero external validation
- **ACD-1**: created by squad leader or approved by one peer — minimal validation
- **ACD-2**: created by product manager or approved by architect — business or technical authority
- **ACD-3**: created by PM AND approved by architect — dual authority

> **Implementation note:** The bundled `extract_jira_swr.py` emits `authority_depth` — how many levels up the parent chain authority was found (0 = direct authority on the leaf ticket, 1+ = inherited from an ancestor). This measures lineage traversal depth, not the full ACD model above, which requires classifying the reporter's organizational role (PM, architect, etc.). The data needed for full ACD (reporter identity) is present in the extracted tickets; role classification requires an org-specific mapping not bundled with the reference tools.

### Intelligence Quotient (IQ)

```
IQ = Valued Decisions / Tokens Consumed
```

Conversion efficiency from input tokens (LLM usage) to valued decisions — decisions that survive contact with reality: a review comment that changed code, a plan that held through implementation, a commit not reverted within 90 days.

### Amplification Ratio

```
Amplification Ratio = CD post-AI / CD pre-AI
```

Time-series comparison measuring whether AI adoption strengthened or weakened an individual's review depth. Ratio > 1 means AI amplified judgment; ratio <= 1 means AI amplified volume without depth.

> **Implementation note:** Framework-defined metric. Reference implementation not bundled — requires monthly extraction runs and time-series comparison. See `tools/README.md` Extending section.

### Foreign Technology Ratio (FTR)

```
FTR = LOC in non-standard stack / Total LOC
```

Fraction of output written in technologies that diverge from the organization's standard stack. High FTR means code cannot be reviewed with depth by peers, cannot be maintained if the author leaves, and cannot benefit from shared libraries.

> **Implementation note:** Framework-defined metric. Reference implementation not bundled — requires a standard-stack definition file per org. The data needed (LOC per language) is present in the extracted commit data.

### Completion Ratio

```
Completion Ratio = Follow-up Fix PRs within 30 days / Original PRs on same code paths
```

Measures the "70% effort" pattern — work that ships but requires re-processing. High completion ratio means shipped PRs generate downstream repair work, indicating incomplete initial conversion.

> **Implementation note:** Framework-defined metric. Reference implementation not bundled — requires code-path overlap detection across PRs within a 30-day window. The data needed (per-file diffs with timestamps) is present in the extracted commit data.

### Combined Signal Matrix

| SWR | CD | Interpretation |
|---|---|---|
| High | High | Deep work on sanctioned priorities — ideal |
| High | Low | Doing the right work shallowly — coaching opportunity |
| Low | High | Deep work on self-directed projects — potential innovation or rogue effort |
| Low | Low | Self-generated shallow work at volume — highest entropy risk |

---

## Acronym Index

| Acronym | Full Name |
|---|---|
| ACD | Authority Chain Depth |
| API | Application Programming Interface |
| ATP | Adenosine Triphosphate |
| CD | Catalyst Density |
| CR | Change Requests |
| CRR | Change Request Rate |
| CS | Catalyst Signal |
| DNA | Deoxyribonucleic Acid |
| DORA | DevOps Research and Assessment |
| FTR | Foreign Technology Ratio |
| IQ | Intelligence Quotient |
| LLM | Large Language Model |
| LOC | Lines of Code |
| PM | Product Manager |
| PR | Pull Request |
| PS | Production Signal |
| ROI | Return on Investment |
| SDLC | Software Development Life Cycle |
| SWR | Sanctioned Work Ratio |
| TDD | Test-Driven Development |
