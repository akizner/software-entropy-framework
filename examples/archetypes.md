# Archetype Profiles — Anonymized Examples

> What the two-axis formula reveals when applied to real extracted data.

---

## How to Read These Profiles

Each profile shows the computed signals from 12 months of GitHub data:

- **PS** (Production Signal) = Commits x Repos Committed
- **CS** (Catalyst Signal) = Reviews x Repos Reviewed
- **CD** (Catalyst Density) = Inline Comments / Reviews
- **CRR** (Change Request Rate) = Change Requests / Reviews

CD color coding: **Green** (>0.7) = substantive, **Yellow** (0.4-0.7) = moderate, **Red** (<0.4) = shallow.

---

## Developer A — System Governor

| Metric | Value |
|---|---|
| PS | 5,220 |
| CS | 8,330 |
| CD | 1.14 (Green) |
| CRR | 0.18 |
| Commits | 290 |
| Repos Committed | 18 |
| Reviews | 490 |
| Repos Reviewed | 17 |
| Inline Comments | 559 |

**Reading:** Dominant on both axes — high production across 18 repos and even higher catalyst output across 17 repos. CD above 1.0 means every review averages more than one inline code comment. CRR of 0.18 means nearly 1 in 5 reviews pushes back with a formal change request. This person's reviews aren't rubber stamps.

**Organizational role:** This profile typically belongs to a senior technical leader who both ships code and actively governs quality across the org. Their direct output (290 commits) understates their impact — the 559 inline comments shaped hundreds of PRs authored by others.

---

## Developer B — Selective Catalyst

| Metric | Value |
|---|---|
| PS | 420 |
| CS | 4,680 |
| CD | 0.52 (Yellow) |
| CRR | 0.07 |
| Commits | 60 |
| Repos Committed | 7 |
| Reviews | 360 |
| Repos Reviewed | 13 |
| Inline Comments | 187 |

**Reading:** Low production (60 commits) but extremely high catalyst signal — 360 reviews across 13 repos. CD in moderate range means some reviews are substantive and some are approvals. CRR of 0.07 means pushback is rare.

**Interpretation caution:** The moderate CD warrants investigation. Is this person doing triage reviews (quick approvals for known-good authors, deep reviews when needed)? Or are they rubber-stamping most and occasionally engaging? The aggregate number doesn't distinguish these — you need to look at the distribution of inline comments per review, not just the average.

---

## Developer C — Production Engine

| Metric | Value |
|---|---|
| PS | 3,780 |
| CS | 144 |
| CD | 0.33 (Red) |
| CRR | 0.00 |
| Commits | 270 |
| Repos Committed | 14 |
| Reviews | 36 |
| Repos Reviewed | 4 |
| Inline Comments | 12 |

**Reading:** High production, near-absent catalyst signal. 270 commits across 14 repos, but only 36 reviews, mostly shallow (CD 0.33), and zero change requests. This person builds but doesn't review.

**Not necessarily a problem:** Some roles are purely production-oriented. The question is whether this person's code gets adequate review from others (check: how many of their PRs have reviews with CD > 0.7?). The concern is when Production Engines work in repos where they're the only committer — their output has no catalyst acting on it.

---

## Developer D — High-Entropy Agent

| Metric | Value |
|---|---|
| PS | 2,940 |
| CS | 1,560 |
| CD | 0.28 (Red) |
| CRR | 0.03 |
| Commits | 210 |
| Repos Committed | 14 |
| Reviews | 156 |
| Repos Reviewed | 10 |
| Inline Comments | 44 |

**Reading:** Strong on both axes — looks like a Hybrid at first glance. But CD of 0.28 reveals the reviews are shallow. 156 reviews with only 44 inline comments means most reviews are approval-only. CRR of 0.03 means almost no pushback.

**The entropy signal:** This person produces a lot AND reviews a lot, but the reviews lack depth. The volume of approvals without substance could be masking quality issues in the PRs they approve. High volume + low density = potential entropy source.

**Investigation prompt:** Pull their review comments — are the 44 inline comments concentrated on a few PRs (selective depth) or spread evenly (consistently shallow)? The distribution changes the interpretation.

---

## Developer E — Depleting Catalyst

| Metric | Value |
|---|---|
| PS | 24 |
| CS | 1,040 |
| CD | 0.89 (Green) |
| CRR | 0.15 |
| Commits | 8 |
| Repos Committed | 3 |
| Reviews | 130 |
| Repos Reviewed | 8 |
| Inline Comments | 116 |

**Reading:** Nearly zero production (8 commits in 12 months) but active, substantive reviews. CD of 0.89 means almost every review includes an inline comment. CRR of 0.15 means regular pushback.

**The depletion signal:** This person has effectively stopped producing code but remains an active quality gate. Possible explanations: transitioning to management, burned out on production, or has become a bottleneck reviewer who reviews instead of building.

**The risk:** If this person leaves, the organization loses a quality gate that shaped 130 PRs. Their reviews are substantive (high CD), so replacing them requires someone with equivalent judgment, not just someone willing to click "approve."

---

## Developer F — Rubber Stamp

| Metric | Value |
|---|---|
| PS | 90 |
| CS | 180 |
| CD | 0.00 (Red) |
| CRR | 0.00 |
| Commits | 30 |
| Repos Committed | 3 |
| Reviews | 45 |
| Repos Reviewed | 4 |
| Inline Comments | 0 |

**Reading:** 45 reviews with zero inline comments and zero change requests. Every review was an approval with no code-level engagement.

**Why this matters:** Every PR this person approved received zero quality gate benefit. If these PRs had no other reviewers, they effectively shipped unreviewed. The review count in GitHub shows 45, but the effective review count is 0.

---

## The Comparison Table

| Developer | Archetype | PS | CS | CD | CRR | Signal |
|---|---|---|---|---|---|---|
| A | System Governor | 5,220 | 8,330 | 1.14 | 0.18 | Governs both production and quality |
| B | Selective Catalyst | 420 | 4,680 | 0.52 | 0.07 | Broad review coverage, moderate depth |
| C | Production Engine | 3,780 | 144 | 0.33 | 0.00 | Builds extensively, rarely reviews |
| D | High-Entropy Agent | 2,940 | 1,560 | 0.28 | 0.03 | High volume both axes, shallow reviews |
| E | Depleting Catalyst | 24 | 1,040 | 0.89 | 0.15 | Deep reviewer, production stopped |
| F | Rubber Stamp | 90 | 180 | 0.00 | 0.00 | Reviews exist, zero substance |

---

## What the Framework Doesn't Tell You

The numbers above are signals, not verdicts. Developer D (High-Entropy Agent) might be a team lead doing quick approval on trusted junior PRs while saving deep reviews for architectural changes — the aggregate CD would still show 0.28. Developer C (Production Engine) might be a new hire who hasn't been added to review rotations yet.

Context is irreducible. The framework tells you where to look. A human has to interpret what they find.
