# Finding and Report Contract

Use these structures for discovery, validation, adjudication, and the final
report. Fields may be serialized as JSON or equivalent structured text between
agents, but paths, symbols, and evidence must remain exact.

## Contents

1. Finder inspection record
2. Finder candidate
3. Deduplicated candidate
4. Validator result
5. Final finding
6. Final report order
7. Inline comments

Records contain concise, externally checkable evidence and decisions. Do not
request or expose hidden chain-of-thought.

## Finder inspection record

Every Finder returns inspection records in addition to candidates:

```text
inspection_id: stable within the review
role: Behavior & Safety | Code Craft | Architecture & Evolution
check_id: BS-* | BS-S* | CC-* | AE-*
review_unit
status: checked_clear | candidate | not_applicable | blocked
applicability_triggers_checked
artifacts_searched
files_and_symbols_read:
  - exact path and symbol or committed object
source_extents_or_objects_read:
  - exact line/byte span or structured object covered
context_read:
  - callers, callees/effect boundaries, contracts, tests, configuration,
    history, or maps actually inspected
inspection_action: concise description of the handbook action performed
supporting_evidence
disconfirming_evidence
verification_attempts:
  - command or static check, result, and limitation
outcome_or_reason
candidate_ids:
  - required when status is candidate
```

`checked_clear` is not a self-attestation: it needs a performed action and
relevant disconfirming evidence. `not_applicable` needs the trigger evaluated,
exact artifacts searched, an inspection action, and evidence that the trigger
is absent; a bare reason is invalid. Every `(role, review_unit)` must account
for the complete role check-ID set exactly once, plus exposed `BS-S*`
supplements. Missing, duplicate, or unknown IDs and every `blocked` record make
the associated unit uncovered. Every candidate links back to at least one
inspection ID.

## Finder candidate

Each Finder returns zero or more records:

```text
candidate_id: temporary stable ID
inspection_ids:
  - originating inspection records
dimension: behavior | security | performance | code-craft | architecture | tests
scope_origin:
  - changed hunk, historical interval, or current whole-codebase symbol
locations:
  - path
  - line or narrow range when available
  - affected symbol or contract
claim: one falsifiable problem statement
triggering_code_or_contract: narrow artifact that triggers the claim
mechanism: how the code produces the failure or change cost
scenario: concrete input, call path, attack, workload, or future change
impact: current failure or maintenance and extension cost
proof_chain: canonical chain from review-rubric.md
evidence:
  - code path, contract, test, history, or measurement
contrary_evidence: evidence already observed against the claim
project_rule_or_contract_source
affected_symbols_or_change_axis
minimal_direction: smallest plausible improvement, not a patch
pattern_action: none | keep | introduce | expand | remove | collapse | replace | disputed
verification_needed: focused checks that could confirm or falsify the claim
```

Finder candidates contain no priority and no confidence. A Finder must return
an empty candidate list when it finds nothing; it must never manufacture a
finding to fill a quota. Candidate records do not replace the inspection
ledger.

## Deduplicated candidate

The main agent merges records only by shared root cause plus affected symbol,
contract, or change axis. The normalized record retains:

- a new anonymous ID;
- scope origin and originating inspection IDs;
- all affected locations;
- one falsifiable claim;
- the narrow triggering artifact and canonical proof chain;
- the combined mechanism and impact;
- strongest supporting and contrary evidence;
- minimal verification required;
- whether abstraction or pattern judgment is involved.

Do not include the Finder's role, identity, wording strength, candidate count,
or self-assessment.

## Validator result

Each fresh Validator returns one record per assigned candidate:

```text
candidate_id
scope_and_origin_check
independent_context_read:
  - exact raw artifacts reopened by the Validator
independent_reconstruction: concise proof chain rebuilt without trusting the Finder
falsification_hypotheses:
  - guard, caller guarantee, contract, test, history, bound, configuration,
    exception, or alternative explanation that could defeat the claim
falsification_attempts:
  - hypothesis, artifact or command checked, result
problem_verdict: Confirmed | Supported | Rejected
proven_mechanism
failure_or_change_scenario
supporting_evidence
contrary_evidence
verification_attempts
evidence_limitations
residual_assumptions
smallest_effective_improvement
pattern_comparison:
  current_design
  minimal_refactor
  patternized_option
pattern_decision:
  action: keep | introduce | expand | remove | collapse | replace | disputed
  judgment: keep | introduce | expand | remove | collapse | replace | defer
  same_evidenced_axis
  participant_semantic_fit
  plausible_named_alternatives
  introduction_or_expansion_gates:
    current_pain
    real_variation_boundary_or_construction_lifecycle_axis
    modification_spread_shrinks
    simpler_option_insufficient
    net_complexity_falls
  removal_or_collapse_gates:
    represented_need_absent_obsolete_or_not_served_by_participants
    demonstrated_indirection_or_misuse_cost
    no_required_boundary_is_lost_or_replacement_improves_it
    smaller_or_replacement_design_reduces_net_complexity
    migration_risk_is_proportionate
  keep_evidence:
    represented_variation_boundary_or_policy
    current_overhead
    counterfactual_removal_touch_set_and_lost_isolation
rejection_reason
```

The `pattern_comparison` and `pattern_decision` sections are required only for
abstraction, interface, extension-point, or design-pattern questions. Only the
gate group appropriate to the action is required; `replace` requires both
introduction and removal groups. `keep` requires `keep_evidence`. Each gate is
a pass/fail subrecord with evidence; a scalar such as `gates: pass` is invalid.
The validator assigns no priority. `Confirmed` and `Supported` have the exact
meanings in `review-rubric.md`; any weaker result is `Rejected`.

`problem_verdict` judges the underlying problem, not the named pattern. A
supported duplication, coupling, or construction problem can coexist with
`pattern_decision.judgment: defer` and a validated minimal refactor. When the
candidate's only claim is that a pattern is missing, failed introduction gates
reject the underlying claim as well.

A Validator cannot support a candidate by restating its prose. The
`independent_context_read`, `independent_reconstruction`, and
`falsification_attempts` fields must be populated. `rejection_reason` is
required for `Rejected`; `residual_assumptions` are explicit for `Supported`.

## Final finding

The main agent converts accepted validator results into:

```text
id: stable sequential ID
priority: P0 | P1 | P2 | P3
dimension
location
verified_problem
failure_or_change_cost
evidence
minimal_improvement
pattern_judgment
change_timing
confidence: Confirmed | Supported
traceability:
  inspection_ids
  validator_candidate_id
```

Requirements:

- The problem statement is a consequence, not a vague quality adjective.
- Location contains the narrowest useful path and line or symbol.
- Evidence is sufficient for another engineer to retrace the reasoning.
- Minimal improvement solves the established cause without speculative
  framework building.
- Pattern judgment says whether to keep, introduce, expand, remove, collapse,
  replace, or defer a pattern and why. When no pattern is relevant, say so
  plainly.
- Change timing is one of: before merge, before release, next related change,
  planned refactor, or optional polish, translated into the request language.
- Priority and confidence remain independent.
- `traceability` is internal audit metadata. In the user report, compress it
  into retraceable evidence rather than exposing internal deliberation.

## Final report order

Write the report in the user's request language while preserving code
identifiers, file paths, refs, and command text. Use this order:

### 1. Scope and interpretation

- Quote or concisely paraphrase the natural-language intent.
- State whether the review covers the whole codebase or directory, current
  development changes, or historical comparisons.
- State the exact resolved baseline and its source, or every historical
  interval.
- For historical review, state that worktree changes were excluded.

### 2. Coverage

Report:

- number and list or compact grouped manifest of included files;
- number and rules or reasons for excluded files;
- number and exact reasons for uncovered files;
- modules and Finder-role completion;
- per-module or per-review-unit expected, returned, missing, blocked,
  `not_applicable`, `checked_clear`, and `candidate` disposition counts;
- applicable-check completion totals by role and any blocked check IDs;
- surrounding context files read but not counted as reviewed changes.

Never claim complete coverage when the uncovered count is nonzero.
Complete coverage also requires missing, blocked, and unvalidated counts to
all equal zero.

### 3. Project rules read

List every applicable instruction, contributor, architecture, requirement, and
test-configuration file. State when none were found.

### 4. Verification

List exact tests, lint checks, type checks, builds, and other checks attempted,
with result and limitation. Include:

- skipped checks and reasons;
- pre-review and post-review repository status comparison;
- unexpected mutations, if any;
- tool failures without multiplying their mechanical diagnostics into
  findings.

### 5. Summary

State:

- overall conclusion;
- exact count by priority and dimension;
- candidate funnel counts: discovered, deduplicated, independently validated,
  Confirmed, Supported, Rejected, and unvalidated;
- important positive evidence when it affects risk;
- for historical comparisons, introduced, eliminated, and persistent issue
  counts plus the observed architecture trend.

Do not use a minimum or maximum finding count. Zero is valid.

### 6. Complete findings table

For a Chinese request, use this exact header:

```text
| ID | 优先级 | 维度 | 位置 | 已验证问题 | 失败/变化成本 | 证据 | 最小改进 | 模式判断 | 修改时机 | 可信度 |
|---|---|---|---|---|---|---|---|---|---|---|
```

For another language, translate the labels but preserve all eleven columns in
the same order:

```text
ID | Priority | Dimension | Location | Verified issue | Failure/change cost | Evidence | Minimal improvement | Pattern judgment | Change timing | Confidence
```

Include every accepted finding and no rejected candidate. Do not truncate,
rank to a top-N list, or add low-confidence filler. When there are zero
findings, include the table header, state that no candidate passed validation,
and still report the per-unit inspection reconciliation and full candidate
funnel. A complete zero-finding result requires zero missing, blocked, and
unvalidated records. Do not substitute "looked good" for check coverage.

### 7. Historical evolution

Include only for multi-interval review:

- interval-by-interval finding summary;
- issues introduced, eliminated, persistent, or transformed;
- abstraction and concept-count trend;
- coupling and dependency-direction trend;
- extension and testing-cost trend.

Trace each trend statement to evidence.

### 8. Rejected abstraction or pattern opinions

Include this section only when a disputed abstraction or pattern proposal was
meaningfully considered and rejected. Use:

```text
| Proposal | Evidence considered | Why not adopted | Simpler decision |
|---|---|---|---|
```

For a Chinese request, title the section `未采纳意见及原因` and translate the
same four columns:

```text
| 意见 | 已考虑证据 | 未采纳原因 | 更简单的决定 |
|---|---|---|---|
```

This table may include only abstraction, interface, extension-point, or
design-pattern proposals. Do not list rejected behavior, security,
performance, code-craft, or ordinary test candidates. Its purpose is to show
how the workflow resisted over-design, not to expose agent deliberation.

## Inline comments

The normal deliverable is the report table. If the host supports inline review
annotations and the user explicitly asks for them, mirror accepted actionable
findings at their narrow code ranges without changing the repository or
posting remotely. Never emit an inline annotation for rejected candidates or
non-actionable praise.
