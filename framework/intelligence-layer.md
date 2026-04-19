# Intelligence Measurement Layer

> Extension of the Entropy Framework for token-to-intelligence conversion measurement.

---

## Problem Statement

The Entropy Framework measures output quality (Production Signal, Catalyst Signal, Catalyst Density, Change Request Rate) but cannot attribute input energy to output value. As AI adoption accelerates per individual contributor, organizations need to measure the conversion efficiency of the full energy pipeline:

```
Tokens In -> Individual -> Intelligence Out -> Value
```

Where "Individual" is agent-agnostic: human, human+AI pair, or autonomous agent.

Energy that doesn't convert to Intelligence is Entropy. The framework already detects entropy in output (shallow reviews, reverted code, unaligned work). What's missing is the input accounting and the authority validation that separates directed intelligence from undirected motion.

---

## The Biological Model Extension

The existing framework maps: Glucose -> Mitochondria -> ATP -> Body Health.

The Intelligence layer adds a parallel energy channel:

| Biological | Organizational (Human) | Organizational (AI) |
|---|---|---|
| Glucose | Salary (constant, not decomposable per action) | Tokens (variable, measurable per API call) |
| Mitochondria | Engineer's judgment + skill | Model capability + prompt quality |
| ATP | Valued decisions, shipped code | Valued decisions, shipped code |
| Heat (waste) | Meetings, context switches, shallow reviews | Hallucinations, rubber-stamp AI output, unread suggestions |
| Free Radicals | Bugs, drift, tribal knowledge | Misaligned AI-generated architecture, vision debt |

Key insight: tokens don't flow in a parallel channel — they flow **through** the human. The combined system efficiency is what matters, not the AI's efficiency in isolation. A human burning 50K tokens to produce a rubber-stamp review has worse Intelligence than one using 2K tokens to produce a surgical inline comment that prevents a production incident.

---

## Proposed Metrics

### Intelligence Quotient (IQ)

```
IQ = Valued Decisions / Tokens Consumed
```

A **Valued Decision** is any output that survives contact with reality:

- A review comment that resulted in code change
- A plan that held through implementation without major deviation
- A commit that wasn't reverted within 90 days
- An architectural choice that didn't cause a post-deploy incident
- A contract specification that downstream implementation matched with high fidelity

**Denominator — Tokens Consumed:**

- For AI agents deployed via API: exact token count from response headers
- For human+AI pairs (IDE copilots): typically blocked without enterprise instrumentation
- Interim proxies: time-between-actions (git timestamps), AI fingerprinting (velocity anomalies, boilerplate patterns), binary AI-assisted classification

IQ is undefined when the denominator is unmeasurable. The framework activates fully when token instrumentation becomes available.

### Intelligence Entropy

```
Intelligence Entropy = Tokens In - (Valued Decisions x Decision Weight)
```

The gap is waste: tokens that produced noise, hallucination, rubber-stamp approvals, code that got reverted, plans that were abandoned.

### Amplification Ratio

```
Amplification Ratio = Catalyst Density post-AI / Catalyst Density pre-AI
```

Does AI make the individual's existing signal stronger or weaker? Time-series comparison before and after AI adoption. If CD improves, AI amplified judgment. If CD stays flat while volume doubles, AI amplified noise. Measurable today from git history — no new instrumentation required.

### Intelligence Decay

Does AI dependency erode native judgment? Measured by: what happens to an individual's CD/CRR when AI access is removed or degraded? If metrics collapse, the intelligence was proxied, not transferred. The biological analogy: IV glucose drips atrophy the digestive system.

---

## Sanctioned Work Ratio (SWR)

### The Problem

The framework measures output quality but not alignment of work to sanctioned technical direction. An individual can score high production, high volume, and still produce pure entropy if the work was never approved by technical authority. Self-created "tech debt" projects approved by one's own squad lead and never reviewed by organizational technical leadership are indistinguishable from legitimate work in the current metrics.

### The Signal

Ticket origin reveals whether work is demand-driven or supply-driven:

| Ticket Creator | Authority Level | SWR Classification |
|---|---|---|
| Product manager / Product owner | Business authority | Sanctioned |
| Architect / Org tech | Technical authority | Sanctioned |
| Engineer, approved by technical authority | Delegated authority | Sanctioned |
| Engineer, approved by own squad leader only | Unverified authority | Unsanctioned |
| Engineer, self-approved or no approval chain | Zero authority | Unsanctioned |

### Heuristic (JIRA-based)

The classification uses ticket hierarchy traversal:

1. If ticket reporter != assignee -> **SANCTIONED**
2. If reporter = assignee, traverse parent chain up to 10 levels
3. If any ancestor has reporter != assignee -> **INHERITED** (authority flows from parent)
4. If entire chain is self-created -> **UNSANCTIONED**

### Authority Chain Depth (ACD)

How many approval layers sit between ticket creation and code execution:

- **ACD-0**: Self-created, self-approved — zero external validation
- **ACD-1**: Created by squad leader or approved by one peer — minimal validation
- **ACD-2**: Created by product manager or approved by architect — business or technical authority
- **ACD-3**: Created by PM AND approved by architect — dual authority

Higher ACD means more organizational energy was invested in validating this work before tokens were burned on it.

> **Implementation note:** The bundled SWR tool emits `authority_depth` (lineage traversal depth: 0 = direct authority on the leaf ticket, 1+ = inherited from ancestor). This is a proxy for ACD but does not classify reporter roles (PM, architect, etc.) as the full model above requires. The reporter identity data is present in extracted tickets; role classification requires an org-specific mapping.

---

## Instrumentation Status

### Available Now (bundled in reference tools)

| Metric | Source |
|---|---|
| SWR | JIRA ticket creator + JIRA-to-GitHub PR linkage |

### Measurable from Extracted Data (not bundled — requires custom implementation)

| Metric | Source | What's needed |
|---|---|---|
| Completion Ratio | Git history — follow-up PRs on same code paths within 30 days | Code-path overlap detection across PRs |
| Knowledge Diffusion | Git log — unique authors per repo, unique reviewers with inline comments | Aggregation script over extracted data |
| Amplification Ratio | Git history time-series — CD computed per quarter | Monthly extraction runs and time-series comparison |
| ACD (full) | JIRA workflow — ticket creator + approval chain | Reporter role classification (PM, architect, etc.) beyond the lineage depth that the bundled tools emit |

### Blocked (requires enterprise IDE instrumentation or API-direct agents)

| Metric | Blocker |
|---|---|
| IQ (full formula) | Token count per action not exposed by IDE |
| Intelligence Entropy | Same — needs token denominator |
| Token-per-Decision | Available only for API-deployed agents (response header usage field) |

### Future (requires organizational change)

| Metric | Dependency |
|---|---|
| Intelligence Decay | Controlled experiment: measure CD with/without AI access |
| Post-mortem Attribution | Incident post-mortem process naming contributing resolver |
| Full IQ across all individuals | Token instrumentation at IDE level |

---

## Open Questions

- **SWR granularity:** Should SWR count at the ticket level or the commit level? A single sanctioned ticket can spawn unsanctioned sub-tasks.
- **Self-created but valuable:** How to handle engineer-created tickets that turn out to be genuinely valuable? SWR flags them, but the framework shouldn't punish initiative — only unvalidated initiative.
- **Agent identity:** When autonomous agents join the system, do they get their own profiles or are they attributed to the human who deployed them? The IQ metric works either way, but organizational accountability may require the human-agent linkage.
