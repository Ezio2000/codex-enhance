# Review Rubric

This rubric defines what each review dimension examines and the proof required
before a candidate can become a finding. Repository rules, documented
contracts, and user-stated concerns take precedence over this generic rubric.

## Contents

1. Shared principles
2. Canonical proof chains
3. Behavior & Safety
4. Code Craft
5. Architecture & Evolution
6. Validator falsification matrix
7. Main-agent adjudication gates
8. Priority
9. Confidence
10. Non-findings

## Shared principles

- Review actual code, tests, configuration, and change history. Do not infer a
  defect from a pattern name, file size, method count, or line-count threshold.
- Prefer the smallest explanation with a traceable mechanism.
- Separate a current failure from a future change cost.
- Distinguish deliberate duplication from accidental duplication. Reuse is
  valuable only when the shared concept and change cadence are genuinely the
  same.
- Judge simplicity by concept count, indirection, coupling, and reader effort,
  not by terseness alone.
- Treat comments as useful when they preserve intent, invariant, tradeoff, or
  external context. Comments that narrate obvious syntax are polish concerns.
- Do not report mechanical style issues that the project's formatter or linter
  can identify. Report the relevant command result instead.
- Tests are part of the design evidence: inspect behavior coverage, seam
  quality, fixtures, determinism, and maintenance cost.
- Smell names, SOLID labels, pattern names, and metrics are search cues, never
  findings. Translate them into a failure, misuse, reader error, invalid state,
  change spread, dependency edge, or test cost.
- For current-development and historical scopes, prove origin in the reviewed
  change or interval. Context may explain a finding but does not widen scope.

## Canonical proof chains

Every candidate and accepted finding must be reducible to one of these chains:

```text
Behavior:
entry and preconditions -> branch/state/data path -> output or side effect
-> violated contract or observable failure

Security:
attacker capability -> untrusted source -> trust crossings and controls
-> sensitive interpreter/operation/data sink -> practical impact

Performance:
reachable trigger frequency -> cost per trigger -> data/resource scale
-> bound, I/O amplification, blocking, exhaustion, or measured impact

Code craft:
real reader or maintenance task -> current concepts/paths/states/tests
-> concrete ambiguity, misuse, navigation, synchronization, or test cost
-> smallest net simplification

Architecture:
real change axis or boundary -> current dependency and modification surface
-> test/release/failure/ownership cost -> status-quo and alternative surfaces

Pattern underlying problem:
one complete behavior, code-craft, or architecture chain above
-> action considered separately from the problem verdict

Pattern introduce or expand:
proven pain -> real same-axis variation, stable boundary, history, or
construction/lifecycle axis -> five admission gates
-> current/minimal/patternized comparison -> introduce, expand, or defer

Pattern keep:
represented variation/boundary/policy -> participant semantic fit
-> current overhead -> counterfactual removal and lost isolation
-> keep or defer to a separately proven removal case

Pattern remove or collapse:
represented need absent, obsolete, or not served -> demonstrated current cost
-> required boundary/policy/invariant/lifecycle preserved
-> smaller design and migration comparison -> remove, collapse, or keep

Pattern replace:
complete removal chain for the old pattern
-> complete admission chain for the new pattern
-> combined migration and three-option comparison -> replace or defer
```

A list of suspicious lines without a closed chain is not a candidate.

## Behavior & Safety

Inspect:

- correctness and behavioral regressions;
- documented and de facto contracts;
- edge cases, state transitions, error propagation, and recovery;
- compatibility across supported inputs, versions, platforms, and callers;
- concurrency, ordering, reentrancy, cancellation, and resource lifetime;
- authorization, trust boundaries, injection, validation, secret handling,
  privacy, and sensitive data flow;
- algorithmic complexity, hot paths, unnecessary I/O, allocation, and
  unbounded work;
- tests that should prove the behavior and meaningful gaps in those tests.

Evidence gates:

- A behavior candidate must show a reproducible failure, a concrete violated
  contract, or an explicit data/control path from input to incorrect outcome.
- A security candidate must identify the attack surface, required attacker
  capability, source-to-sink or sensitive-data path, and practical impact.
- A performance candidate must identify complexity growth, a credible hot
  path, redundant or blocking I/O, a resource bound, or measurement. General
  claims such as "might be slow" are insufficient.
- A test-gap candidate must tie the missing test to a demonstrated risky path
  or contract, not merely to uncovered lines.

## Code Craft

Inspect:

- names that reveal or obscure the domain model;
- control flow, early exits, error paths, and local reasoning burden;
- unnecessary concepts, flags, modes, layers, and indirection;
- accidental repetition and opportunities for honest reuse;
- comments, public contracts, and discoverability;
- types, states, ownership, nullability, and enforced invariants;
- cohesive function and class responsibilities;
- test readability, fixtures, brittleness, and diagnostic value.

Evidence gates:

- Show the exact reader or maintainer ambiguity.
- Show repeated logic that represents one stable concept and is likely to
  change together before recommending extraction.
- Show an invalid state or contract the type system could feasibly prevent
  before recommending a stronger type.
- For simplification, name the concept or branch that disappears and confirm
  that behavior remains expressible.
- For naming or readability, identify a realistic misreading, incorrect usage,
  or maintenance delay. Pure personal preference is not a finding.

## Architecture & Evolution

Inspect:

- cohesion and ownership of responsibilities;
- coupling, dependency direction, cycles, and boundary leakage;
- domain logic embedded in transport, storage, UI, or framework layers;
- module and package seams;
- openness to evidenced extension and closure against needless modification;
- change propagation across files and modules;
- pattern fitness, abstraction cost, and accidental frameworks;
- test seams and the ability to replace true external boundaries;
- speculative generality and YAGNI.

Evidence gates:

- A design candidate must name a concrete current maintenance cost or a
  realistic change scenario and trace the files, symbols, or branches it
  affects.
- An OCP candidate must identify a real variation axis or stable external
  boundary; "may need another implementation someday" is insufficient.
- A coupling candidate must identify the dependency and show how it expands
  change, test, release, or failure scope.
- A boundary candidate must identify ownership that is currently unclear or
  violated and its observable cost.
- Every new or removed abstraction, interface, extension point, or named
  design-pattern proposal must pass the challenge in `pattern-fit.md`.

## Validator falsification matrix

Validators do not grade Finder prose. They independently rebuild the claim
from raw artifacts and perform the relevant checks below.

| Check | Independent reconstruction | Required falsification attempts | Support gate | Reject when |
|---|---|---|---|---|
| `V-01 Behavior` | Recreate entry, preconditions, control/data/state path, expected contract, and actual observable result. | Search for dominating guards, caller guarantees, earlier normalization, alternate branches, intentional contract text, and tests proving the alleged path unreachable or correct. | Reproduction/targeted failing check, or authoritative contract plus an unambiguous reachable trace. | Path is unreachable, contract differs, guard closes it, result is intentional, origin is outside scope, or a material link is assumed. |
| `V-02 Security and privacy` | Recreate attacker capability, source, identity/trust crossings, transforms, controls, sink, and impact. | Check authorization at the sink, context-correct encoding/parameterization, canonicalization, unforgeable identity binding, deployment isolation, redaction, least privilege, and safe defaults. | A controllable source reaches a protected sink through missing or bypassable controls with practical impact. | Attacker cannot reach/control the source, an effective control dominates the sink, deployment assumption is established, impact is only a dangerous API name, or the data is not sensitive. |
| `V-03 Performance and resources` | Derive trigger, frequency, scale variables, operation/I/O/allocation count, bounds, and user/system impact. | Search for strict limits, batching, indexes, caching, backpressure, cold-path evidence, compiler/runtime behavior, query plans, profiles, and measurements that bound or refute cost. | Measurement, query plan, or a complete cost model tied to a realistically reachable hot or unbounded path. | Scale is strictly small, path is not operationally relevant, optimization already bounds it, the cost model omits dominant behavior, or impact is speculative. |
| `V-04 Code craft` | Recreate the realistic read/change/test task and current names, concepts, paths, invariants, or reuse sites involved. | Check project terminology, complete call sites, domain irreducibility, differing owners/change cadence, valid reasons for indirection, behavior-preserving alternatives, and concept cost added by the suggestion. | A concrete misuse, invalid state, synchronized change, navigation burden, or brittle-test cost remains and the minimal improvement reduces net concepts/cost. | Preference is personal, duplication is incidental, complexity is inherent, alternative adds equal/greater concepts, or a mechanical tool owns the issue. |
| `V-05 Architecture and evolution` | Recreate module owners, dependency/change path, public contracts, construction, and current touch/test/release/failure surface. | Check documented boundaries, cohesive transaction needs, stable dependency contracts, independent deployment/version cadence, historical counterexamples, and costs introduced by the proposed boundary. | A real change or failure demonstrably spreads across unrelated owners/surfaces, or a current boundary violation has concrete cost. | Scenario is hypothetical, touch points are cohesive/inherent, dependency is stable and correctly directed, alternative increases coordination, or history does not support the claimed axis. |
| `V-06 Abstraction and pattern` | Recreate the underlying problem separately from the proposed pattern action; then recreate the represented pain, same-axis boundary/variation or construction/lifecycle invariant, participants, lifecycle, callers, and three options. | Apply the action-specific gates in `pattern-fit.md`; try deletion, rename/move, function extraction, data/table, stronger type, and one-boundary isolation before a named pattern. Check participant semantic fit and compare another named pattern when clearly plausible. | The underlying problem has its own complete proof chain. Introduce/expand requires all admission gates; remove/collapse requires all removal gates; replace requires both; keep requires retention/counterfactual-removal evidence. | Reject the problem only when its proof fails. Otherwise defer the named pattern when its gates fail and retain the proven minimal improvement. A missing-pattern-only claim is rejected when any admission gate fails. |
| `V-07 Test gap` | Recreate the already-proven risk path and enumerate tests at relevant unit, integration, contract, and end-to-end layers. | Check whether an existing test reaches the branch indirectly, whether its oracle observes the consequence, whether static/type guarantees prevent the risk, and whether mocks/fixtures alter the path. | A demonstrated risk has no effective oracle and the missing check would fail under the concrete regression. | Risk itself is rejected, another test covers it with a useful oracle, or the proposed test checks implementation/coverage rather than behavior. |

Every Validator result records artifacts independently read,
`independent_reconstruction`, each `falsification_attempt`, supporting and
disconfirming evidence, verification attempts, residual assumptions, and the
decisive reason for the verdict.

For `V-06`, `problem_verdict` and `pattern_decision.judgment` are independent.
Do not discard a proven local duplication, invalid-state, coupling, or
construction problem merely because Strategy, Builder, Repository, or another
named solution is not justified.

## Main-agent adjudication gates

The main agent applies every gate in order. Failure at any gate rejects the
candidate; later gates cannot rescue it.

| Gate | Required decision |
|---|---|
| `D-01 Scope` | Confirm the location, affected contract, and `scope_origin` belong to the resolved review scope. Context-only and pre-existing issues are excluded where required. |
| `D-02 Project rule` | Resolve applicable root and nested rules and conflicts. A generic preference cannot override an explicit repository contract. |
| `D-03 Evidence closure` | Replay the appropriate canonical proof chain and confirm the Validator independently reconstructed and tried to falsify it. |
| `D-04 Root cause` | Deduplicate only by shared root cause plus affected symbol, contract, or change axis; preserve distinct causes with similar symptoms. |
| `D-05 Impact and priority` | Assign priority from demonstrated consequence and timing, never Agent count, rhetoric, file size, or confidence label. |
| `D-06 Minimal improvement` | Tie the improvement directly to the cause and state which concept, path, invalid state, dependency, or change touch point disappears. |
| `D-07 Pattern judgment` | Require the three-option comparison and the complete action-specific record: admission gates for introduce/expand, removal gates for remove/collapse, both for replace, or retention evidence for keep. Keep the underlying problem verdict separate. If any introduction gate fails, use the equivalent of "do not introduce a pattern yet" while preserving any independently validated minimal-refactor finding. |
| `D-08 Traceability` | Ensure the final evidence cell links back to exact code/contracts/tests/history, Validator record, and Finder inspection IDs without exposing private chain-of-thought. |

## Priority

Priority measures impact and urgency, not confidence.

- **P0** — a demonstrated security compromise, data loss or corruption, or
  runtime issue that blocks a critical path. Use sparingly and only with
  direct evidence.
- **P1** — a high-probability behavioral risk or a high-leverage structural
  issue whose change or failure blast radius is already material.
- **P2** — demonstrated maintainability, reuse, or extensibility debt with a
  concrete recurring or upcoming cost.
- **P3** — evidence-backed code-craft, clarity, or readability concern that
  still requires engineering judgment.

Do not elevate priority because a change is large, a Finder sounds certain, or
a fashionable pattern is absent.

## Confidence

Confidence is independent of priority and has exactly two allowed values:

- **Confirmed** — directly reproduced, measured, asserted by an authoritative
  contract plus an unambiguous reachable path, or proven by an unambiguous
  data/state/dependency path.
- **Supported** — strongly supported by code, tests, history, or a concrete
  change scenario with a complete trace and no decisive counterevidence, but
  not directly reproduced or measured. State why direct execution was not
  available when it would otherwise be appropriate.

Anything below `Supported` is rejected. Do not use percentages, "High",
"Medium", "Low", or any other confidence label.

## Non-findings

Do not report:

- formatter or linter trivia as repeated line-level findings;
- hypothetical extensions without evidence;
- personal naming or style preferences without maintenance impact;
- harmless one-time duplication;
- a single implementation behind an interface solely because it has one
  implementation;
- a Factory solely because it currently creates one product;
- a Wrapper solely because it delegates;
- a missing pattern name when the current design is clear and localized;
- a request for more tests without a risky unverified behavior;
- a code smell, SOLID acronym, complexity score, implementation count, or line
  threshold without a canonical proof chain;
- an issue outside the requested scope or a pre-existing issue not introduced
  or worsened in an incremental interval;
- code outside the resolved scope.

A single implementation can be justified by a stable external boundary,
ownership boundary, test seam, or compatibility layer. Conversely, a
pass-through abstraction is still questionable when it adds no boundary,
policy, invariant, or change isolation. Decide from evidence, not shape.
