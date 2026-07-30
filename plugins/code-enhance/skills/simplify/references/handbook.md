# Simplify Finder Handbook

This handbook is normative for the Simplify Finder. Find complexity that can
be deleted, collapsed, or localized while preserving behavior and required
boundaries. Smaller source text alone is not simplification.

## Contents

1. Execution order
2. Preservation proof
3. Mandatory check matrix
4. Candidate and completion gates

## 1. Execution order

For every assigned review unit:

1. Read the complete unit, construction and registration paths, relevant
   callers and callees, state and effects, tests, compatibility rules, and
   history when reachability or intent depends on it.
2. Reconstruct at least one normal use, one failure or boundary use, and one
   realistic maintenance task.
3. Enumerate `SM-01` through `SM-09` exactly once for the unit. Record
   `checked_clear`, `candidate`, justified `not_applicable`, or `blocked`.
4. For a suspected issue, identify exactly what can disappear and compare the
   current and minimal surfaces.
5. Search for dynamic use, supported compatibility, domain invariants,
   ownership, external isolation, lifecycle, concurrency, and other evidence
   that requires the current complexity.
6. Return the complete inspection ledger even when there are no candidates.

## 2. Preservation proof

Every candidate must include:

```text
removable_item:
  kind: concept | control_path | state | api_surface | configuration |
        mutation_or_coordination_path | test_mechanism | dead_path
  exact_symbols_or_edges
current_surface:
  concepts
  decisions_or_paths
  states
  construction_or_navigation_hops
  modification_touch_set
minimal_surface:
  concepts
  decisions_or_paths
  states
  construction_or_navigation_hops
  modification_touch_set
preserved_behavior:
  outputs
  side_effects_and_order
  errors_and_recovery
  supported_inputs_and_compatibility
  concurrency_and_lifecycle
preserved_boundaries:
  external_system
  ownership_or_transaction
  deployment_or_version
verification_or_static_proof
```

The lists need not contain artificial numeric scores. They must name the
actual elements that remain or disappear. If any required behavior or boundary
cannot be established, reject the suggestion or mark the inspection blocked;
do not guess.

For current-development review, report only complexity introduced or
materially worsened by the change. For historical review, attribute it to one
interval. For whole-codebase or directory review, assess current first-party
code.

## 3. Mandatory check matrix

| Check | Required inspection | Candidate evidence | Disconfirming evidence | Ledger payload |
|---|---|---|---|---|
| `SM-01 Control paths and local decisions` | Enumerate branches, loops, exits, callbacks, retries, modes, and relevant effect order. Walk normal, failure, and boundary paths. Compare guard clauses, table/data representation, direct sequencing, or branch consolidation without changing behavior. | Name the exact decision, branch, mode, or navigation step removed and show the same cases and effect ordering remain covered with fewer paths. | Complexity mirrors irreducible domain decisions; alternatives hide coupled logic, duplicate behavior, or alter ordering/recovery; the issue is only visual nesting. | `decisions_and_paths`, `cases_preserved`, `effect_order`, `removable_path`, `minimal_flow` |
| `SM-02 Responsibility and symbol-level cohesion` | List a unit's responsibilities, owned data, invariants, side effects, and reasons to change. Inspect callers, collaborators, and tests. Compare keeping, moving a local operation, merging split fragments, or dividing an unrelated responsibility. | A concrete task currently crosses unrelated responsibilities or duplicated coordination; the minimal move/merge/split removes a responsibility hop or synchronized edit without transferring module ownership. | Responsibilities jointly preserve one invariant or lifecycle; separation adds coordination or exposes internals; the required fix changes architectural ownership and belongs to Design. | `responsibilities`, `owned_invariants`, `maintenance_task`, `current_touch_set`, `removable_coordination`, `minimal_local_shape` |
| `SM-03 Concepts and indirection` | Trace complete construction, registration, delegation, and use paths through wrappers, interfaces, factories, registries, adapters, mappers, base classes, flags, and generic frameworks. Name the policy, invariant, boundary, lifecycle, or real variation each hop owns. | A hop owns none of those needs, while imposing navigation, configuration, debugging, fixture, or synchronized-edit cost; collapsing it preserves required boundaries. | The hop isolates an external or ownership boundary, centralizes policy, protects an invariant, manages lifecycle, or absorbs evidenced variation; removal increases coupling. | `use_case`, `concepts_and_hops`, `value_per_hop`, `current_cost`, `removable_concept`, `boundary_preservation` |
| `SM-04 Duplication and honest reuse` | Compare every suspected site by semantics, invariant, owner, callers, variation, and change cadence. Simulate one evidenced change. Compare deliberate duplication, data/table extraction, a local helper, or reuse of an existing concept. | Sites represent one stable concept, should change together, and currently create divergence or repeated modification; the option removes repeated decisions or touch points without mode flags or branch explosion. | Similarity is incidental; owners or cadence differ; reuse requires flags/callbacks or creates a new abstraction; duplication is small and isolates volatile policy. | `sites`, `shared_concept`, `owners`, `change_cadence`, `change_simulation`, `reuse_option`, `net_concept_change` |
| `SM-05 State, flags, and transitions` | Enumerate state variables, flags, valid combinations, transitions, writers, readers, caches, and duplicated derived values. Trace initialization through disposal or transfer. | A state is derivable, duplicated, transiently invalid, or exists only to coordinate avoidable phases; removing or deriving it eliminates a state or transition while preserving lifecycle and observables. | State represents durable domain information, an external checkpoint, required cache, concurrency coordination, or transaction boundary; derivation is more costly or changes semantics. | `states_and_flags`, `valid_combinations`, `transitions`, `writers_and_readers`, `removable_state`, `lifecycle_proof` |
| `SM-06 API and configuration surface` | Inspect declarations, implementations, all relevant callers, defaults, extension hooks, configuration sources, compatibility promises, and tests. Identify parameters, exports, modes, and hooks that no supported use requires. | A surface is unused or needlessly exposes an internal choice, and its removal/privatization eliminates invalid combinations, caller ceremony, or synchronized changes without breaking supported consumers. | Public compatibility, reflection, generation, runtime registration, or an evidenced extension requires it; uncertainty about external consumers cannot prove removal. | `surface`, `callers_and_consumers_checked`, `supported_uses`, `compatibility_basis`, `removable_option`, `smaller_contract` |
| `SM-07 Mutation, side effects, and coordination` | Trace values from producers through aliases, writes, callbacks, implicit context, lazy evaluation, caches, and consumers. Record ordering and ownership. | Localizing or eliminating a mutation/effect removes an alias, temporal dependency, setup step, or synchronization path while preserving externally visible effects and required ordering. | Shared state is explicit and required by lifecycle, transaction, concurrency, or performance; copying or localization changes identity/ordering or adds more coordination. | `value_or_effect`, `owner`, `aliases_and_writes`, `ordering_constraints`, `removable_coordination`, `preserved_effects` |
| `SM-08 Test scaffolding and maintenance paths` | Trace setup → trigger → observation through fixtures, factories, mocks, snapshots, helpers, and cleanup. Compare production seams and multiple representative tests. | A helper, mock layer, fixture state, or assertion mechanism adds no domain meaning and causes repeated setup, brittle edits, hidden behavior, or poor failure localization; removing it preserves the behavior oracle. | Integration setup is required; fixture expresses stable domain language; mock isolates a true external boundary; snapshot is the contract; proposed removal weakens the oracle. | `tests`, `behavior_oracle`, `scaffolding_path`, `maintenance_cost`, `removable_mechanism`, `oracle_preservation` |
| `SM-09 Dead, obsolete, and speculative paths` | Establish reachability and ownership for unused branches, flags, deprecated adapters, unreferenced exports, compatibility shims, commented code, and future hooks. Search runtime registration, reflection, supported configurations, migration/rollback plans, tests, and history. | The path is unreachable or unused under supported configurations, or its represented need has expired, while retention creates current navigation, testing, or modification cost; removal risk is bounded. | Dynamic or external use exists; compatibility, migration, or rollback remains active; the seam isolates a real boundary; removal risk cannot be established. | `symbol_or_path`, `references_checked`, `dynamic_use`, `compatibility_or_migration_basis`, `current_cost`, `removal_risk` |

## 4. Candidate and completion gates

Apply all gates before returning a candidate:

- Close the code-craft proof chain from `review-rubric.md`.
- Complete the preservation record in section 2.
- Name the exact item removed and show a lower net concept, path, state,
  surface, coordination, or maintenance burden.
- Compare the status quo with the smallest behavior-preserving alternative.
- Reject an alternative that merely moves complexity or adds equal/greater
  concepts.
- Exclude presentation, performance, architecture, security, and ordinary
  correctness claims. Do not recommend a named design pattern.

Return:

```text
role: Simplify
review_kind: simplify
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
  - records from finding-contract.md with primary_review_kind: simplify
```

`checked_clear` records the action and evidence that defeated a candidate.
`not_applicable` records the evaluated trigger, artifacts searched, action,
and evidence proving absence. `blocked` makes the unit uncovered. Complete all
nine checks after finding an issue; there is no candidate quota.
