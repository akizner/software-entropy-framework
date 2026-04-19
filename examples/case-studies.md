# Organizational Case Studies — Anonymized Patterns

> Patterns observed when applying the Entropy Framework to real engineering organizations.

---

## Case 1: The Metabolic Plateau

**Situation:** Mid-size engineering org (~50 developers), consistent sprint velocity for 18 months. Leadership reports "stable throughput." No visible crisis.

**What the framework detected:**

Extracting 12 months of GitHub data and computing signals revealed:

- **Catalyst Density org-wide had dropped from 0.65 to 0.31** over the period. Reviews were happening (the count was stable), but inline comments had collapsed. Reviews had become approvals.
- **Three developers accounted for 70% of all inline comments.** Remove those three, and the org's effective CD drops below 0.15 — rubber-stamp territory.
- **Code that shipped in months 1-6 had a 12% follow-up fix rate within 30 days.** Code shipped in months 7-12 had a 28% follow-up fix rate. Something that got approved was increasingly broken.

**The metabolic plateau:** Sprint velocity was constant. PRs merged on schedule. The output metrics looked healthy. But the quality of the review process had degraded silently. The repair mechanism (code review as mitophagy) was failing, and the damage was accumulating as downstream fix PRs.

**What happened next:** Two of the three high-CD reviewers left in the same quarter. The follow-up fix rate jumped to 41%. "Suddenly" things were breaking — but the degradation had been measurable for months.

**Framework signal that would have caught it early:** Track CD distribution across the org, not just the average. When the number of developers with CD > 0.7 drops below a threshold, the quality gate is concentrating in too few people. That concentration is a leading indicator of organizational fragility.

---

## Case 2: The Sanctioned Work Ratio Divergence

**Situation:** Two squads in the same org, similar size, similar velocity metrics. Leadership treats them as equivalent.

**What SWR revealed:**

| | Squad Alpha | Squad Beta |
|---|---|---|
| Average SWR (strict) | 0.82 | 0.31 |
| Average SWR+I (relaxed) | 0.91 | 0.48 |
| Unsanctioned ticket ratio | 9% | 52% |

Squad Alpha's work overwhelmingly traced to tickets created by product management or architectural authority. Squad Beta's work was more than half self-created — the engineers were creating their own tickets, assigning them to themselves, and executing.

**Digging deeper:** Squad Beta's unsanctioned tickets fell into two categories:

1. **Legitimate technical debt work** that the team knew needed doing but nobody in product had prioritized (~30% of unsanctioned tickets). These tickets had good descriptions, linked to known production issues, and the code changes were substantive.

2. **Technology exploration projects** using non-standard stack components (~22% of unsanctioned tickets). These tickets had vague descriptions, no parent epics, and the code introduced dependencies the rest of the org couldn't review effectively.

**The nuance:** SWR doesn't say "unsanctioned = bad." It says "unsanctioned = unvalidated by organizational authority." Category 1 was valuable work that should have been sanctioned but wasn't (a product backlog failure). Category 2 was genuine entropy — work that consumed resources without organizational alignment.

**Action taken:** Product was asked to review and formally sanction the Category 1 work. Category 2 work was paused pending architectural review. The SWR metric didn't make the decision — it made the pattern visible so humans could interpret it.

---

## Case 3: The AI Amplification Test

**Situation:** Organization rolled out AI coding assistants to all developers. Leadership wanted to measure ROI.

**Traditional measurement:** Lines of code per developer increased 40%. PR throughput increased 25%. Leadership declared success.

**What the Entropy Framework measured:**

Comparing 6 months pre-AI to 6 months post-AI:

| Metric | Pre-AI | Post-AI | Change |
|---|---|---|---|
| PRs per developer per month | 8.2 | 10.3 | +25% |
| LOC per PR (median) | 120 | 280 | +133% |
| CD (org average) | 0.58 | 0.39 | -33% |
| Follow-up fix rate (30 day) | 14% | 23% | +64% |
| Review cycle time (hours) | 6.2 | 4.1 | -34% |

**The Amplification Ratio:** CD post-AI / CD pre-AI = 0.39 / 0.58 = **0.67**

AI had amplified volume, not judgment. Developers were shipping more code, but the review process couldn't keep up. PRs were bigger (+133% LOC), reviews were faster (-34% cycle time) but shallower (-33% CD), and the downstream damage rate increased (+64% follow-up fixes).

**The thermodynamic interpretation:** More fuel was being poured into the system (tokens generating more code), but the conversion machinery (reviews, quality gates) wasn't strengthened. More input through degraded mitochondria produces more heat and more free radicals, not more useful work.

**The honest conclusion:** AI increased individual production velocity. It did not increase organizational intelligence. The 25% throughput increase came with a 64% increase in downstream repair work. Net organizational efficiency may have decreased.

---

## Case 4: The Invisible Catalyst

**Situation:** Senior developer leaves the org. Their individual metrics are unremarkable: moderate commits, moderate PRs, middle of the pack on most dashboards.

**What the framework revealed when computed retrospectively:**

| Metric | The Departed | Org Average |
|---|---|---|
| PS | 1,200 | 1,450 |
| CS | 3,800 | 890 |
| CD | 1.32 | 0.48 |
| Cross-boundary review ratio | 0.71 | 0.22 |
| Repos reviewed | 22 | 6 |

This person's PS was below average — unremarkable on any production-focused dashboard. But their CS was 4x the org average, their CD was nearly 3x, and they reviewed across 22 repos (vs org average of 6). 71% of their reviews were on repos outside their own team.

**The impact after departure:**

In the quarter following their departure:

- Cross-team review rate dropped 18% org-wide
- CD on repos they had regularly reviewed dropped from 0.61 to 0.34
- Two architectural drift incidents occurred in repos where they had been the primary reviewer

**Why traditional metrics missed it:** They didn't show up on any "top performer" list because those lists rank by production. Their contribution was catalytic — they improved the quality of other people's output without appearing in the output themselves. The reaction rate differential (org performance with them vs without) was only visible retrospectively.

**Framework lesson:** Track CS and CD separately from PS. Catalysts are invisible to production metrics. Their departure causes damage that manifests weeks later in repos they no longer review.

---

## Pattern Summary

| Case | What Looked Healthy | What Was Actually Happening | Framework Signal |
|---|---|---|---|
| Metabolic Plateau | Stable velocity | Review quality collapsing silently | CD decline + reviewer concentration |
| SWR Divergence | Two squads, same throughput | One squad 52% unsanctioned work | SWR per squad |
| AI Amplification | +25% throughput | +64% downstream repair rate | Amplification Ratio < 1.0 |
| Invisible Catalyst | Average-looking developer | 4x catalyst impact, cross-org quality gate | CS/CD decoupled from PS |

---

## The Common Thread

Every case follows the same pattern: the metrics that organizations typically track (velocity, throughput, PR count) showed health or improvement. The metrics the Entropy Framework tracks (CD, SWR, Amplification Ratio, cross-boundary review distribution) revealed accumulating disorder underneath.

Measuring output measures fuel consumption. Measuring entropy measures the health of the conversion machinery. They answer different questions.
