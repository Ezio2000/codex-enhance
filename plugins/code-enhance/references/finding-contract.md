# Shared Finding Contract

Use these records across all Code Enhance specialties. Preserve raw evidence
between stages, but strip identity, rhetoric, priority, and confidence before
independent validation.

## Contents

1. Inspection ledger
2. Finder candidate
3. Deduplicated candidate
4. Validator result
5. Final finding
6. Report contract

## 1. Inspection ledger

Return one row for every handbook check ID and review unit:

```text
inspection_id
review_kind
check_id
review_unit
status: checked_clear | candidate | not_applicable | blocked
applicability_triggers_checked
artifacts_searched
files_and_symbols_read
source_extents_or_objects_read
context_read
inspection_action
supporting_evidence
disconfirming_evidence
verification_attempts
scope_origin
outcome_or_reason
candidate_ids
```

`source_extents_or_objects_read` must identify complete symbols, ranges, or
committed objects—not only filenames or diff hunks. `not_applicable` requires
positive absence evidence. `blocked` is never equivalent to coverage.

## 2. Finder candidate

Use this schema:

```text
candidate_id
review_kind
check_ids
scope_origin
location
affected_symbol_boundary_or_axis
claim
proof_chain
root_cause
observable_or_maintenance_cost
supporting_evidence
disconfirming_evidence
context_read
verification_attempts
minimal_improvement
related_review_kinds
residual_assumptions
```

The required `proof_chain` depends on `review_kind`:

- `beautify`: current expression -> concrete reading or visual ambiguity ->
  affected maintenance task -> clearer expression that preserves behavior and
  structure.
- `simplify`: current concepts/branches/states/hops -> demonstrated reasoning
  or synchronization cost -> exact removable element -> proof that behavior
  and design boundaries remain expressible.
- `standardize`: reachable workload -> size variables -> operation/I/O/
  allocation model or measurement -> evidenced cost -> idiomatic or efficient
  alternative with tradeoffs.
- `design`: current owner/dependency/boundary/variation -> concrete change or
  lifecycle cost -> minimal boundary improvement -> pattern action and gates
  when applicable.
- `security`: attacker or untrusted actor -> controllable input/state ->
  missing or bypassed control -> sink/effect -> confidentiality, integrity, or
  availability impact.

Ordinary behavior correctness, generic reliability, compatibility, or test
coverage is not independently reportable. It may appear only as evidence for
one of the five proof chains.

Do not assign final priority or confidence in a Finder candidate.

## 3. Deduplicated candidate

After root-cause deduplication, use:

```text
deduplicated_candidate_id
primary_review_kind
related_review_kinds
source_candidate_ids
root_cause
affected_symbol_boundary_or_axis
scope_origin
claim
specialty_proof_chain
supporting_evidence
disconfirming_evidence
minimal_improvement
validator_context
```

Exactly one `primary_review_kind` is required. The main agent selects it by
the minimal effective improvement rules in `orchestration.md`, not by Finder
order or vote.

## 4. Validator result

Use:

```text
validator_result_id
deduplicated_candidate_id
primary_review_kind
independent_context_read
independent_reconstruction
falsification_hypotheses
falsification_attempts
supporting_evidence
disconfirming_evidence
residual_assumptions
specialty_gate_results
verdict: Confirmed | Supported | Rejected
verdict_reason
```

The Validator must independently reopen raw evidence. A restatement of the
candidate is not reconstruction.

Specialty gates:

- `beautify`: reject purely personal taste when no project convention,
  concrete ambiguity, or repeated reading cost exists.
- `simplify`: reject line-count reduction that preserves the same concepts or
  hides behavior; prove which concept, branch, state, hop, or surface
  disappears.
- `standardize`: reject “faster,” “cleaner,” or “more idiomatic” without a
  pinned-version basis plus a cost model, reachable workload, bound analysis,
  benchmark, profile, or query-plan evidence.
- `design`: use the action-specific introduction, retention, removal,
  collapse, expansion, or replacement gates in `pattern-fit.md`.
- `security`: reject claims without a reachable source-to-effect path and a
  concrete confidentiality, integrity, or availability impact.

## 5. Final finding

Only `Confirmed` and sufficiently evidenced `Supported` candidates may become
findings:

```text
finding_id
primary_review_kind
related_review_kinds
priority: P0 | P1 | P2 | P3
confidence: high | medium
location
verified_issue
failure_or_change_cost
evidence
minimal_improvement
pattern_judgment
change_timing
scope_origin
validator_result_id
```

Priority reflects impact, not preference:

- `P0`: immediate catastrophic security impact with a demonstrated path.
- `P1`: high-impact exploitable risk or design/performance cost likely to
  cause serious operational or evolution failure.
- `P2`: concrete, recurring maintenance, performance, boundary, or
  defense-in-depth cost.
- `P3`: localized but evidenced readability, simplification, idiom, or
  hardening improvement.

Use `pattern_judgment: not_relevant` outside `design`. For design, use one of:

```text
keep | introduce | expand | remove | collapse | replace | defer
```

## 6. Report contract

Report these sections even when there are zero findings:

1. Interpreted scope and baseline or intervals.
2. Invoked review kinds.
3. Included, excluded, and uncovered coverage.
4. Project rules and references read.
5. Verification commands and results.
6. Candidate funnel counts:
   - discovered;
   - deduplicated;
   - validated;
   - confirmed/supported;
   - rejected;
   - missing, blocked, and unvalidated.
7. Findings table.
8. Rejected design-pattern proposals, when relevant.

Use this findings table:

| ID | Priority | Review kind | Location | Verified issue | Failure/change cost | Evidence | Minimal improvement | Pattern judgment | Change timing | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|

Do not include rejected ordinary candidates. Never omit uncovered scope or
failed verification to make a zero-finding report appear complete.
