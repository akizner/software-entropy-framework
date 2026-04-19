# Human Codex

> **Version:** 1
> **Status:** Accepted
> **Created:** April 2026

---

## Preamble

Agentic execution transfers authority over implementation to the agent. This document codifies what the human must continue to provide — regardless of how capable the agent becomes.

A governed Software Development Life Cycle (SDLC) addresses the artifact layer: contract as source of truth, Test-Driven Development (TDD) cycles as the atomic unit of execution, hard gates at Definition and Plan, autonomous execution between. What it does not yet codify is the human side of the contract — the signal the human owes the system for the agent's vector of work to remain aligned with reality.

Agency is a vector multiplier. A well-specified contract yields correct code at speed. A poorly-specified contract yields wrong code at the same speed — and the test suite cannot detect the error, because the tests verify conformance to the contract, not alignment to reality. The human is not a bottleneck to be reduced. The human is the governor whose quality bounds system health.

The four pillars below are not suggestions. They are the minimum signal the human owes the system. Where implementation can be delegated, these cannot.

---

## Pillar 1 — Declare what counts as success

Every contract requires the approver to state, in their own words, what outcome makes the work worth doing. This statement is independent of the test suite. Tests verify that the code does what the contract says. They do not verify that the contract was worth writing.

The discipline is simple: if all the tests pass, will this have been worth doing? Why? Write the answer down, in the approver's voice, before the gate closes.

The failure mode is invisible without this pillar: contracts that satisfy every Functional Requirement and every assertion, and that nobody remembers approving because there was nothing to remember. Ceremonial approval.

### Enforcement

- **Artifact layer:** The task specification must contain a "Success Criterion" section — present, non-empty, written in the approver's voice. Must not be a paraphrase of Functional Requirements.
- **Gate layer:** The approver must state the success criterion in writing before the hard gate closes.
- **Reviewer layer:** Flag any specification where Success Criterion restates Functional Requirements, is empty, or uses only test-centric language (e.g., "all tests pass," "contract is satisfied").

---

## Pillar 2 — Bear the consequences

Every contract has one named human approver who accepts accountability for the outcome. Not a team. Not a role. A person — known, recorded, identified, accountable.

This is uncomfortable. That is the point. Diffused accountability is not accountability — it is plausible deniability dressed up as governance. When a contract produces a bad outcome, the postmortem must point at a person who said "ship it." That person's future approvals will be better for the experience.

The pillar does not require the approver to be senior, certified, or expert. It requires them to be named, present, and willing.

### Enforcement

- **Artifact layer:** An "Approved-By" field populated with exactly one human identity.
- **Commit trailer:** Non-empty. Matches a known engineer. Singular — not a list.

---

## Pillar 3 — Curate context

The agent can read the code, the contract, the repository documentation, and the commit history. It cannot read the room.

Organizational history, team politics, stakeholder trust, tribal knowledge, known constraints that live only in someone's head — these enter the agentic system only through the human. If the approver does not transfer this context into the contract, the contract is produced in a vacuum, and the resulting code is technically correct and organizationally naive.

Curation is not decoration. Name the stakeholders. Name the affected teams. Name the constraints that would surprise someone outside the situation. If the context section is empty, the contract is incomplete — regardless of how detailed the Functional Requirements are.

### Enforcement

- **Artifact layer:** An "Organizational Context" section is present and names at least: stakeholders, affected teams, and known constraints (political, historical, or cross-team).
- **Reviewer layer:** Flag contracts where Organizational Context is empty, generic ("affects backend engineers"), or derivable from the codebase without human input.

---

## Pillar 4 — Calibrate trust

Approval is provisional. The approver is not certifying that the contract is correct — that axis is being out-scaled by the agent. The approver is certifying that their uncertainty is within the band where deferring to the agent is sound, and declaring the conditions under which the contract should be re-opened.

Every contract carries a confidence band — HIGH, MEDIUM, or LOW — and at least one re-review trigger. Triggers are events, metrics, or timelines: "re-review if latency regresses beyond 200 ms"; "re-review at 30 days post-ship"; "re-review if the owning team changes." Low-confidence contracts require a second approver before proceeding.

This pillar is what keeps the governance layer alive past the moment of approval. Without it, every gate is terminal. With it, every gate is a hypothesis with explicit conditions for revisiting.

### Enforcement

- **Artifact layer:** A "Confidence & Re-review Triggers" section with one of HIGH / MEDIUM / LOW and at least one named trigger (event, metric, or timeline).
- **Commit trailer:** Confidence enum (HIGH | MEDIUM | LOW). LOW requires a second approver on the commit.

---

## Amendment

This document governs its own evolution. Any proposed change requires a Governance Review that evaluates the change against all four pillars. A change may ship only if each pillar is preserved, or if the change is accompanied by a Governance Decision Record acknowledging the trade-off, naming the mitigation, and approved by the architecture forum.

The goal is not to freeze the framework — it is to make degradation visible and deliberate.

---

## Enforcement Kill Switch

The top-level enforcement state (active or suspended) is a circuit breaker. When suspended, the review mechanism still runs and logs audit metadata, but emits no blocking outcomes (advisory only). This exists so that a pathological false-positive cycle can be interrupted without a revert; activating the kill switch is itself a governance-scope change and must be justified on the next Governance Review.

---

## Scope

This Codex applies to:

- The governed SDLC flow end-to-end: brief-to-task, task-to-plan, plan-to-implement, design-review, pre-PR-review, bug-fix, archive.
- The Decision Record lifecycle and schema.
- The git trailer schema for SDLC trailers.
- This document itself.

It does not apply to ad-hoc engineering work outside the governed flow. That is not a loophole — it is a boundary. Work that is not governed is not amplified by governance, and not constrained by it.

---

## Connection to the Entropy Framework

The Human Codex is **mitophagy** — the repair mechanism that keeps the governed SDLC healthy. The Entropy Framework measures whether that repair mechanism is functioning.

Without the Codex, the governed SDLC degrades silently: approval becomes ceremonial, context goes unstated, accountability diffuses, trust calibration stops. The metrics look fine because the process still runs. But the conversion machinery is damaged, and entropy accumulates underneath.

The Codex ensures that every contract passing through the governed pipeline carries the four signals the agent cannot generate: success criteria, accountability, organizational context, and calibrated trust. The Entropy Framework measures whether those signals are actually present and whether they improve outcomes. Governance without measurement is treatment without diagnosis. Measurement without governance is diagnosis without treatment.

Together, they form the organizational immune system.
