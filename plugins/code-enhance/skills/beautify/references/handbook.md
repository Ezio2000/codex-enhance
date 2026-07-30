# Beautify Finder Handbook

This handbook is normative for the Beautify Finder. Inspect how clearly the
existing behavior is presented. Do not redesign or simplify it.

## Contents

1. Execution order
2. Scope and mechanical-tool boundary
3. Mandatory check matrix
4. Candidate and completion gates

## 1. Execution order

For every assigned review unit:

1. Read the complete unit, nearby declarations, relevant callers or uses,
   project style rules, and tests that reveal its intended vocabulary.
2. Reconstruct a realistic reading, debugging, review, or local-edit task.
3. Enumerate `BF-01` through `BF-05` exactly once for the unit. Record
   `checked_clear`, `candidate`, justified `not_applicable`, or `blocked`.
4. For a suspected issue, identify the exact visual cue, term, order, or prose
   that causes a plausible misreading, misuse, navigation cost, or delay.
5. Search for formatter or linter ownership, repository conventions, stable
   external terminology, and other disconfirming evidence.
6. Return the complete inspection ledger even when there are no candidates.

## 2. Scope and mechanical-tool boundary

- For current-development review, report only presentation costs introduced or
  materially worsened by the change.
- For historical review, attribute each cost to one interval.
- For whole-codebase or directory review, assess the current first-party code.
- Do not emit line-by-line findings for formatter or linter rules. Record the
  exact read-only command and summarize its result under verification.
- A formatter-owned deviation can become a candidate only when the repository
  does not mechanically enforce it and evidence establishes a separate
  reader or maintenance consequence.
- Do not use preference, line length, identifier length, nesting depth, or
  inconsistency count alone as evidence.

## 3. Mandatory check matrix

| Check | Required inspection | Candidate evidence | Disconfirming evidence | Ledger payload |
|---|---|---|---|---|
| `BF-01 Layout and visual grouping` | Read complete declarations and executable units. Trace how indentation, whitespace, delimiter placement, dense expressions, and grouping communicate structure and relatedness. Check the repository's formatter and nearby canonical code. | A specific visual cue makes unrelated operations appear related, hides a boundary, or forces a realistic reader to rescan or navigate incorrectly; identify the minimal layout-only correction. | A formatter owns the form; grouping mirrors one invariant or atomic sequence; the alternative separates code that must be read together; the difference is taste only. | `visual_cue`, `implied_structure`, `actual_structure`, `reader_task`, `mechanical_owner`, `minimal_presentation_change` |
| `BF-02 Naming and domain vocabulary` | Build a term-to-meaning map from definitions, relevant uses, domain types, requirements, errors, configuration, and tests. Check one-term/one-meaning, hidden units/state, misleading verbs, generic placeholders, and vocabulary drift. | State the name's implied meaning, actual meaning, exact caller or maintainer misreading, and resulting misuse, navigation, or delay. | The term is an explicit project or external-contract convention; type and scope remove ambiguity; the distinction is meaningful; rename would create vocabulary drift. | `term`, `implied_meaning`, `actual_meaning`, `uses_read`, `project_vocabulary`, `misreading_or_delay` |
| `BF-03 Expression and local narrative order` | Walk declarations, guards, transformations, side effects, and result construction in reading and execution order. Check whether prerequisites precede uses, related expressions remain adjacent, and abstraction levels change without a visible narrative boundary. | A realistic reader must jump backward/forward, retain an unstated dependency, or infer ordering that a presentation-only reorder or extraction can make explicit without removing paths or changing behavior. | Order is semantically required; moving code would obscure lifecycle or error ordering; the supposed problem requires deleting branches or introducing abstractions and therefore belongs elsewhere. | `reader_task`, `current_reading_order`, `execution_constraints`, `navigation_or_memory_cost`, `presentation_only_option` |
| `BF-04 Comments, docstrings, and nearby intent` | Classify material prose as contract, invariant, rationale, tradeoff, workaround, or syntax narration. Compare it with code, tests, requirements, and history when rationale is historical. Inspect missing prose only for non-obvious intent that code and types cannot express safely. | Stale, misplaced, or syntax-narrating prose misleads or obscures the code; or an absent invariant/rationale creates a concrete unsafe reading or maintenance delay. Give the smallest update, move, or removal. | Code, types, or authoritative docs already express the fact; the prose preserves durable external rationale; adding commentary would merely narrate syntax. | `statement_or_missing_intent`, `kind`, `source_of_truth`, `match`, `reader_impact`, `minimal_prose_change` |
| `BF-05 Local consistency and scanability` | Compare adjacent, semantically equivalent constructs, public API presentation, error text, tests, and project-established idioms. Distinguish consistent appearance from forced uniformity across different concepts. | Equivalent local concepts use conflicting visual or linguistic forms that cause a concrete wrong association, missed relationship, review burden, or inconsistent diagnostic interpretation. | Forms encode a real semantic distinction; the project intentionally supports both; standardization would hide domain differences; a mechanical rule fully owns it. | `equivalent_concepts`, `forms_compared`, `project_basis`, `semantic_distinction`, `scan_or_diagnostic_cost`, `consistent_option` |

## 4. Candidate and completion gates

Apply all gates before returning a candidate:

- Close the code-craft proof chain from `review-rubric.md`.
- Name the realistic reader or maintenance task and the exact presentation
  feature causing cost.
- Show why repository terminology or a mechanical tool does not already settle
  the issue.
- Keep the direction presentation-only. It may rename, reorder, regroup,
  reformat, update prose, or improve local discoverability, but must not remove
  behavior, concepts, paths, states, APIs, or boundaries.
- Exclude performance, architecture, security, and ordinary correctness
  claims.

Return:

```text
role: Beautify
review_kind: beautify
inspection_ledger:
  - inspection_id
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
    outcome_or_reason
    candidate_ids
candidates:
  - records from finding-contract.md with primary_review_kind: beautify
```

`checked_clear` records the action and evidence that defeated a candidate.
`not_applicable` records the evaluated trigger, artifacts searched, action,
and evidence proving absence. `blocked` makes the unit uncovered. Complete all
five checks after finding an issue; there is no candidate quota.
