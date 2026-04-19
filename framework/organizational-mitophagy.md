# Organizational Mitophagy — Self-Improvement Loops as Repair Mechanisms

> Reverse engineering agentic self-improvement patterns into engineering SDLC.

---

## TL;DR

The most interesting open-source AI agent frameworks implement a "self-improvement" loop that is not learning in the ML (Machine Learning) sense — no weight updates, no training at runtime. It is structured procedural memory with disciplined retrieval. That's actually the interesting part, because the entire pattern is portable to human organizations.

The mapping hypothesis: the agentic learning loop is a concrete, working implementation of **mitophagy** from the Entropy Framework. It's the repair mechanism that captures learnings and feeds them back before context evaporates.

---

## The Agentic Pattern (Stripped of Marketing)

Five-step loop observed in self-improving agent architectures:

1. **Receive** — input arrives (any channel)
2. **Retrieve** — full-text search over past sessions + skill documents
3. **Reason & Act** — LLM (Large Language Model) uses loaded skills + memory to drive tool calls
4. **Document** — after complex task (trigger: 5+ tool calls), agent autonomously writes/updates a structured skill document
5. **Persist** — outcome, user preferences, new knowledge stored for future retrieval

Key design decisions in the storage layer:

- **Skill documents** — structured Markdown with YAML frontmatter, organized in folders with optional scripts, references, and assets
- **Memory file** — environment facts, conventions, lessons learned. Hard character cap (typically ~2,200 characters)
- **User profile** — individual preferences and communication style. Hard character cap (~1,375 characters)
- **Session index** — full-text indexed archive of all past sessions, retrieved on-demand

Loading strategy uses **progressive disclosure**: Level 0 is names and descriptions only (~3k tokens, always in context). Level 1 is the full skill loaded when triggered. Level 2 is a specific reference file within a skill. Minimizes context waste.

**Self-patching**: when the agent encounters information that contradicts or extends an existing skill, it rewrites the skill during use. Not a separate "update the doc" task.

---

## Primitive to SDLC (Software Development Life Cycle) Mapping

| Agent Primitive | Purpose | SDLC Equivalent |
|---|---|---|
| Complex-task trigger (5+ tool calls) | Automatic capture, no human judgment call | PR > N LoC (Lines of Code), incident at Sev-2+, any cross-squad dependency, feature > X story points |
| Autonomous skill generation | Doc is written while context is hot | Mandatory "learning artifact" at feature close, generated from ticket + PR + review thread |
| Skill document (YAML + Markdown) | Standard, portable format | Team runbook format with frontmatter: trigger, preconditions, procedure, pitfalls, verification |
| Progressive disclosure (L0/L1/L2) | Minimize context waste | Index of learnings in onboarding, full doc on demand, runbooks/code references on pull |
| Full-text search + LLM summarization | Searchable recall, not dumpster | Searchable org knowledge with LLM-summarized retrieval, not Confluence sprawl |
| Skill self-patches during use | Repairs happen in same workflow | Engineer amends learning doc in the PR where the contradiction appears, not in a follow-up ticket |
| Memory file (hard character cap) | Size pressure forces consolidation | Team runbook with hard size cap — forces pruning, prevents slop accumulation |
| User profile (per-individual) | Captures individual working style | Engineer profile: review style, tradeoff patterns, domain expertise — survives departure |
| Security scanner on skills | Prevents poisoned docs | Peer review with structured checks before merge to team knowledge base |
| Cross-agent skill standard | Portability | Cross-squad interoperable format — Squad A's learning loadable by Squad B |
| Skill usage telemetry | Which skills fire, which rot | Learning-doc hit-rate metric — dead docs get deprecated |

---

## The Four Critical Design Decisions

### 1. Bounded memory with hard caps

Memory is capped at ~2,200 characters. Not "keep it concise" — literally capped. This is the single most important design decision. Most organizational knowledge bases fail because they have no size pressure, so they accumulate slop. Size pressure forces consolidation, which forces quality.

**SDLC implication:** team runbooks should have enforced size budgets. Pick a number (8KB, 10 entries). When full, adding requires removing.

### 2. Automatic triggers, not human judgment

Skills get generated because the complexity threshold was crossed. No human decided "this is worth documenting." That's the only way it works at scale — humans are systematically bad at recognizing what's worth capturing, and they're terrible at doing it retrospectively.

**SDLC implication:** triggers must be observable automatic events. PR-size thresholds, incident severity, cross-team JIRA dependencies, reviewer count. Never "when you think it's worth it."

### 3. Progressive disclosure

Level 0 is just names and descriptions. The agent browses the shelf; it doesn't read every book. Humans work the same way — a 40-page runbook that nobody opens is worse than a 5-line index entry pointing to a 2-page runbook that gets read.

**SDLC implication:** every team runbook needs a one-line description surfaced in onboarding/search, full doc only on pull. Index separately from content.

### 4. Self-patching in-flight

When a skill is wrong, the agent fixes it during the task that exposed the contradiction — not in a separate task that never gets prioritized. This is the only way docs stay current.

**SDLC implication:** the doc update must be a blocking part of the same PR that revealed the stale doc. Not a TODO. Not a follow-up ticket. Same merge.

---

## Failure Modes When Applied to Humans

1. **Humans are worse at documentation than agents.** Agents generate skill docs deterministically when triggered; engineers skip the doc because "this feature is unique." Need to either automate the first draft via LLM over the PR/ticket then require human signoff, or make doc the merge gate.

2. **Size caps get resented.** Engineers will argue "this is important, we need more room." The discipline of deletion is culturally hard. Requires tech-lead enforcement, not guidelines.

3. **Self-patching requires contradiction detection.** Agents detect contradictions because they're reading the doc in-context. Engineers often don't read the doc before coding. Fix: the PR template asks "does this change invalidate any existing runbook entry?" as a required field.

4. **Skills become process hacks instead of knowledge.** Teams will abuse the mechanism to encode administrative procedures rather than engineering knowledge. Need a taxonomy that distinguishes operational/procedural/architectural knowledge.

---

## Concrete Implementation Pattern

**Triggers (automatic, via CI/CD + issue tracker webhooks):**
- PR touching >300 LoC OR >3 files in different services
- Any issue ticket with parent in a different squad
- Any incident at Sev-2+
- Any feature with >3 reviewers or >5 rounds of review

**Capture (LLM-generated first draft):**
- On trigger, an agent reads PR title/description/diff + issue ticket + review thread, drafts a learning document following the team template
- Draft gets attached to the PR as a comment. Engineer edits/approves before merge.

**Storage (in the repo, not in a wiki):**
- `/docs/runbooks/` in each service repo, with enforced entry cap per folder
- Index file at repo root listing all runbooks with one-line descriptions (Level 0)

**Retrieval:**
- Onboarding doc is the index. New hires pull what they need.
- LLM-backed search over runbooks, surfaced in team chat.
- Metric: runbook hit-rate per quarter. Entries with zero hits get flagged for pruning.

**Self-patching gate:**
- PR template adds checkbox: "Does this change invalidate any existing runbook? If yes, update in this PR or explain why not."
- Reviewer can't approve without the box being filled.

---

## Tie-in to the Entropy Framework

Runbook hit-rate becomes a new Catalyst signal. High hit-rate = mitophagy functioning. The repair mechanism is alive.

Runbook age without update, despite high adjacent PR activity = damaged repair mechanism. The docs exist but they've stopped absorbing the lessons that adjacent work is producing.

This is a measurable analogue to the metabolic plateau: if PRs keep shipping but the runbooks they should reference are stale, you're accumulating entropy silently. The knowledge produced by work is evaporating instead of being captured. That's organizational free radical production — invisible damage from a process that looks healthy.

---

## The Honest Critique

"Does it learn or just memorize?"

These systems memorize. There's no weight update. The "self-improvement" is a retrieval system over a growing corpus of procedural notes. That's not less valuable — for an engineering organization, memory + retrieval is exactly the right abstraction because you don't want behavior drift, you want accumulated institutional knowledge that new hires can load.

The distinction matters because when you map this to SDLC, you're mapping the memory+retrieval pattern, not any kind of actual learning. That's the right ceiling to aim for.
