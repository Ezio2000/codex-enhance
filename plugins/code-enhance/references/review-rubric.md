# Shared Evidence and Validation Rubric

Apply this rubric before returning, validating, or adjudicating a candidate.
The specialty handbook defines inspection coverage; this file defines evidence
quality and false-positive resistance.

## Contents

1. Shared evidence rules
2. Specialty proof requirements
3. Validator falsification
4. Adjudication

## 1. Shared evidence rules

Every candidate must establish:

```text
scope origin
complete relevant context
current mechanism
concrete cost or security impact
minimal effective improvement
disconfirming evidence
verification or explicit limitation
```

Prefer project rules, pinned versions, complete control/data/dependency paths,
measurements, tests, and history over generic best practices. A diff hunk is
an entry point, not sufficient context. Read complete symbols plus relevant
callers, owners, configuration, tests, and history.

Zero is valid. Never invent a target number of findings, reward novelty, or
promote a claim because multiple Finders repeated it.

Reject:

- style preference without a concrete readability cost or project basis;
- shorter code that preserves the same concept count or hides behavior;
- performance claims without a hot path, reachable scale, bound analysis, or
  measurement;
- abstraction claims based on shape, implementation count, or SOLID slogans;
- security claims without an attacker-controlled source, control failure,
  reachable effect, and CIA impact;
- ordinary correctness, reliability, compatibility, or test-gap claims that
  do not satisfy one of the five specialty proof chains.

## 2. Specialty proof requirements

### Beautify

Establish the exact reading, visual, naming, or intent ambiguity and the
realistic maintenance task it slows or misleads. Project formatting and naming
rules are strong evidence. Formatter output alone is not a separate finding
unless it exposes a coherent, in-scope readability cause.

Reject:

- personal taste;
- demands for more comments that narrate syntax;
- renames without a plausible misreading;
- proposals that delete concepts or change public structure.

### Simplify

Count concepts, decisions, states, indirection hops, mutation sites, public
surface, and synchronized edits for one real use or change task. Name the
exact element that disappears and prove behavior and existing design
boundaries remain expressible.

Reject:

- fewer lines with equal or higher concept count;
- collapsing a real external or ownership boundary;
- deduplication across semantically different owners;
- deletion whose reachability or compatibility cannot be established;
- pattern changes that belong to `design`.

### Standardize

Pin the language, framework, database, or protocol version. State size
variables and derive operation, I/O, allocation, queue, or blocking cost.
Prefer benchmarks, profiles, query plans, and operational evidence. When only
static analysis is possible, name the reachable workload and bounds.

Reject:

- “modern,” “clean,” or “best practice” without a project or version basis;
- micro-optimization outside a reachable workload;
- performance differences dominated by noise or unsupported assumptions;
- ordinary correctness or compatibility concerns;
- recommendations that require changing ownership or a public boundary.

### Design

Name the owner, dependency edge, boundary, variation axis, lifecycle, or
transaction boundary and the concrete change or maintenance cost. For every
abstraction or named pattern, keep the underlying problem verdict separate
from the pattern judgment and use `pattern-fit.md`.

Reject:

- diagram or directory aesthetics;
- speculative extensibility;
- accidental duplication presented as a shared concept;
- a single implementation used as proof against an interface;
- pattern introduction when a minimal local refactor solves the cost.

### Security

Build an end-to-end path:

```text
actor -> controllable source -> transformations -> missing/bypassed control
-> sink/effect -> confidentiality/integrity/availability impact
```

Establish authentication and authorization context, deployment assumptions,
data sensitivity, existing guards, realistic capability, and blast radius.
Never retrieve or print live secrets during verification.

Reject:

- a dangerous API with no untrusted path;
- a theoretical race without attacker influence or CIA impact;
- a dependency concern without affected version and reachable use;
- generic hardening advice presented as an exploit;
- pure resource cost without an abuse or availability path.

## 3. Validator falsification

For every deduplicated candidate, a fresh Validator records:

1. **V-01 Scope:** Is the mechanism in the resolved scope and attributable to
   the requested change or interval?
2. **V-02 Context:** Were complete symbols, callers, owners, configuration,
   and relevant tests or history read?
3. **V-03 Trigger:** Is the claimed input, workload, maintenance task,
   variation, or attacker capability reachable?
4. **V-04 Guards:** Do existing types, bounds, ownership, validation,
   permissions, caching, batching, or lifecycle controls falsify it?
5. **V-05 Cost:** Is the readability, complexity, performance, design, or CIA
   consequence concrete and proportionate?
6. **V-06 Alternative:** Does the minimal improvement actually remove the
   proven cost without shifting it elsewhere?
7. **V-07 Specialty boundary:** Is this the correct primary review kind, and
   is any related kind merely evidence rather than a duplicate finding?
8. **V-08 Verification:** Was the narrowest safe falsification attempted, or
   is the limitation explicit?

Return:

- `Confirmed` when the mechanism and cost are directly demonstrated;
- `Supported` when the evidence is strong but one bounded assumption remains;
- `Rejected` when the path, cost, ownership, scope, or specialty gate fails.

## 4. Adjudication

The main agent alone:

1. reconciles coverage before judging candidates;
2. deduplicates by root cause and affected axis;
3. assigns one primary review kind by minimal effective improvement;
4. requires a fresh Validator result;
5. weighs project rules and measured evidence before generic guidance;
6. assigns priority and confidence only after validation;
7. reports all and only validated findings.

Do not decide by vote, Finder identity, confidence averaging, or highest
suggested severity. A validated underlying problem may survive while its
suggested pattern or optimization is rejected; report the smallest supported
improvement.
