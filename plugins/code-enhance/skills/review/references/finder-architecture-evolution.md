# Architecture & Evolution Finder Handbook

This handbook is normative for the Architecture & Evolution Finder. It
reviews architecture through ownership, dependency, and real change—not
through diagram aesthetics, pattern counts, or abstract SOLID labels.

## Contents

1. Required maps and execution order
2. Scope-origin rule
3. Mandatory check matrix
4. Cross-module and historical passes
5. Completion and output

## 1. Required maps and execution order

Before evaluating architecture, build only the parts of these maps that touch
the assigned scope:

```text
module_map: module -> responsibility -> owned state/invariants -> public entry
dependency_map: source -> target -> kind -> contract -> direction
change_map: real variation/change -> touched symbols/files/tests/config/owners
construction_map: entry -> registration/factory/DI -> runtime implementation
external_boundary_map: local contract -> external system -> adapter/lifecycle
```

Then:

1. Read architecture rules and module/build boundaries.
2. Trace at least one complete use case across every affected boundary.
3. Enumerate `AE-01` through `AE-13` for every review unit and return exactly
   one disposition for each. A `not_applicable` outcome records the trigger,
   artifacts searched, action, and evidence proving absence.
4. Use history only when it can establish ownership, variation, or repeated
   change; never treat age or churn alone as a defect.
5. For every abstraction or pattern question, apply `pattern-fit.md` and
   compare current design, minimal refactor, and patternized design.
6. Search for counterexamples and costs of the proposed alternative.
7. Return the maps used, inspection ledger, and candidates.

## 2. Scope-origin rule

- Current-development findings must be introduced or materially worsened by
  the change. A changed caller may expose a pre-existing boundary problem only
  when the new path makes its cost newly real.
- Historical findings must identify the interval that introduced,
  eliminated, persisted, or transformed the issue.
- Whole-codebase findings describe current cost.

Every design claim must name a present maintenance cost or a credible,
evidence-backed change scenario. "Violates SOLID," "not scalable," "not
clean," and "may need more implementations" are not mechanisms.

## 3. Mandatory check matrix

| Check | Applicability and minimum context | Required inspection | Candidate evidence | Disconfirming evidence | Minimum verification | Ledger payload |
|---|---|---|---|---|---|---|
| `AE-01 Module responsibility and ownership` | Applicable to every module/package/component and cross-module use. Read public entries/exports, internal owners, state/schema, callers, tests, and architecture rules. | Map responsibility, owned data, invariants, and public contract. Trace callers that read or mutate owned state. Identify orphaned, duplicated, or competing ownership. | A responsibility/invariant has no clear owner, two modules enforce it differently, or callers bypass the public boundary, causing concrete synchronization, invalid-state, or maintenance cost. | Cross-boundary use is an explicit stable contract; shared ownership is transactional and documented; moving responsibility would split one invariant or increase coordination. | Trace a complete use and failure path across the boundary and identify the owner at each state change. | `module`, `responsibility`, `owned_state`, `invariants`, `public_contract`, `bypass_or_competing_owner` |
| `AE-02 Dependency direction and cycles` | Applicable to imports, calls, data/schema dependencies, runtime registration, configuration, build artifacts, and release dependencies. Read both sides, build/module config, entry/registration, and tests. | Record dependency kind and intended direction. Detect cycles, inner-policy dependence on outer mechanisms, initialization order, and compile/runtime/release coupling. | A concrete edge or cycle makes stable policy depend on volatile detail, forces coordinated release/init, broadens tests/failures, or blocks replacement. | Target is a smaller stable contract; edge follows documented architecture; apparent cycle is type-only/tooling-only with no change/runtime cost; inversion adds more unstable API. | Use existing dependency tooling if read-only, or give exact source/target symbols and the resulting change or runtime path. | `from`, `to`, `dependency_kind`, `contract`, `intended_direction`, `cycle`, `consequence` |
| `AE-03 Boundary leakage and domain/infrastructure separation` | Applicable where domain decisions meet transport, storage, UI, frameworks, vendors, or platform APIs. Read domain rule, boundary code, alternate entries, persistence/schema, and tests. | Trace where policy is decided and where external representations are translated. Check duplicated rules across entry points and infrastructure types leaking into stable domain APIs. | A domain change or external-technology replacement touches unrelated layers, rules diverge across entries, or tests must instantiate infrastructure to exercise pure policy. | The rule is itself boundary policy; external type is the stable contract; separation would duplicate mapping or expose a larger interface. | Simulate one concrete domain-rule change or boundary replacement and list the touch set. | `domain_rule`, `current_owner`, `external_detail`, `leak_edges`, `change_scenario`, `affected_layers` |
| `AE-04 Coupling and modification propagation` | Applicable to changes spanning files/modules/config/tests/owners. Read all affected definitions, callers, registrations, tests, history for the same axis, and release boundaries. | Pick a real past, current, or explicitly planned change axis. Enumerate implementation, branch, config, fixture, test, documentation, and release touch points and their owners. Separate inherent work from accidental propagation. | One coherent change requires synchronized edits across unrelated owners or stable modules, widens test/release/failure scope, or repeatedly creates omission risk. | Touch points form one cohesive transaction; centralizing would create a god module; the change is a one-time migration; apparent fan-out is generated/mechanical. | Compare current touch set with the smallest feasible ownership or boundary change; use history when it demonstrates repeated propagation. | `change_axis`, `touch_set`, `owners`, `inherent_work`, `accidental_spread`, `test_release_failure_scope` |
| `AE-05 Encapsulation and public surface` | Applicable to exported types/functions, extension hooks, configuration keys, shared schemas, and internal state exposed across boundaries. Read declarations, consumers, versioning/compatibility rules, and tests. | Identify what consumers truly require versus what is exposed. Check leaked representation, write access, unstable lifecycle, broad interfaces, and extension points that reveal internals. | Consumers depend on internal representation or lifecycle, making an internal change externally breaking or allowing invalid state; a smaller stable contract serves current uses. | Surface is a deliberate external standard; consumers need the full capability; narrowing would create chatty or duplicated APIs; compatibility forbids immediate change. | Inspect all relevant consumers and compare required operations with exposed operations and invariants. | `surface`, `consumers`, `required_capabilities`, `exposed_details`, `break_or_misuse_scenario`, `minimal_contract` |
| `AE-06 OCP and evidenced variation axis` | Applicable to repeated conditionals, registries, variants, plugins, providers, state kinds, platform branches, and recurring extension work. Read every variant, selection/construction logic, stable core, tests, and relevant history. | Name the variation axis. Determine whether variants share a stable contract, change independently, and repeatedly edit stable code or scattered switches. Simulate adding one realistic variant. | Real variants or historical additions repeatedly modify stable unrelated code, duplicate same-axis decisions, or force unrelated tests; an extension seam would shrink the touch set. | Domain has one stable case; branch is local and exhaustive; new case is speculative; table/data or one extraction solves it; polymorphism merely relocates the switch. | Produce before/after touch sets for a real or credible near-term variant and apply the five gates in `pattern-fit.md`. | `variation_axis`, `variants`, `selection_sites`, `stable_core_edits`, `history`, `new_variant_touch_set` |
| `AE-07 Abstraction, interface, and extension-point fitness` | Applicable to interfaces, base classes, generics, wrappers, factories, registries, callbacks, plugin points, and proposals to add/remove them. Read all implementations, construction/registration, callers, tests, boundary role, and history. | State the abstraction's contract and represented variation/boundary. Compare it with implementations. Count concepts, configuration, navigation, and synchronized edits; test substitutability and contract stability. | Abstraction leaks implementations, owns no policy/boundary/variation, or adds current cost; or its absence duplicates a stable contract and spreads real change. Admission/removal gates must be explicit. | One implementation validly isolates an external/ownership boundary or lifecycle; interface is smaller/stabler than implementation; direct code is clearer for one local case. | Complete the action-specific admission, removal, replacement, or retention record plus the three-option comparison; do not decide by implementation count. | `abstraction`, `contract`, `pattern_action`, `represented_boundary_or_variation`, `implementations`, `callers`, `current_cost`, `gate_record` |
| `AE-08 Named design-pattern fitness` | Applicable only when code already uses a recognizable pattern or a concrete problem may warrant one. Read the full participant lifecycle, construction, call paths, variants, failure modes, tests, and history. | Identify the underlying pain before naming a pattern and keep its verdict separate. Evaluate whether participant roles match the same evidenced axis, whether the pattern localizes change, and what concepts/configuration/failure modes it adds. For removal/overuse, test whether the represented variation never existed or is obsolete and whether a smaller design preserves required isolation. Use the decision cards in `pattern-fit.md`. | Missing/introduction requires current cost plus real same-axis variation/boundary and all admission gates. Misuse/overuse/removal instead requires the removal gates: demonstrated overhead or semantic mismatch, preservation by a smaller design, and proportionate migration risk; it need not invent real variation. | Shape alone; pattern is idiomatic but harmless; minimal refactor is enough for an introduction claim; participant semantics do not match; distribution hides rather than removes branching; removal loses a valid boundary; migration cost dominates. | Record the underlying problem verdict, pattern action/judgment, current/minimal/patternized surfaces, and the appropriate action-specific gates. Compare another named pattern when clearly plausible. | `pain`, `problem_verdict`, `pattern_action`, `pattern_candidate_or_existing`, `same_evidenced_axis`, `participants`, `three_options`, `action_specific_gate_record`, `judgment` |
| `AE-09 External boundaries and test seams` | Applicable to network, persistence, clock, randomness, filesystem, process, platform, vendor, and other independently failing systems. Read local contract, adapter/implementation, lifecycle, callers, substitutes, and contract/integration tests. | Check whether the local contract reflects domain needs rather than vendor surface, owns translation/failure/lifecycle policy, and permits focused tests without duplicating the implementation. | External detail leaks across modules, failure cannot be simulated locally, vendor changes spread broadly, or test substitutes must reproduce a huge unstable surface. | A single Adapter correctly isolates a stable boundary; direct standard-library use is tiny and stable; real integration is the only meaningful test; extra seam adds no isolation. | Simulate a vendor failure or replacement and list production/test changes. | `external_system`, `local_contract`, `translation_and_policy`, `leaks`, `replacement_touch_set`, `test_seam_cost` |
| `AE-10 Shared concepts across modules` | Applicable to duplicated domain rules, schemas, constants, protocols, validation, or utilities across modules. Read all sites, ownership boundaries, deployment/version cadence, callers, and history. | Determine whether sites encode one authoritative concept or intentionally independent bounded contexts. Compare shared kernel, generated contract, local duplication, and translation at boundaries. | One concept has conflicting owners or drifts across modules, causing compatibility/correctness/change cost; a clear owner or shared contract reduces that cost. | Similar terms differ semantically; modules deploy/change independently; sharing creates lockstep coupling; explicit translation protects bounded contexts. | Trace one real concept change and compatibility path across modules, including version skew. | `concept`, `sites`, `semantics_per_site`, `owners`, `change_cadence`, `drift`, `sharing_or_translation_option` |
| `AE-11 Runtime composition, global state, and operational boundary` | Applicable to DI/service locators, globals/singletons, registries, startup/shutdown, feature flags, configuration, caches, and deployment units. Read composition root, initialization, lifecycle, concurrency, test setup, and operational config. | Trace how implementations/state/config are selected, initialized, shared, refreshed, and shut down. Check hidden dependencies, order sensitivity, ambient context, flag combinations, and failure isolation. | A use cannot declare/test its dependencies, startup order is fragile, global mutation couples tests/requests, invalid configuration combinations are reachable, or one failure expands an unrelated runtime/deployment domain. | Process-wide singleton is the true lifecycle; composition root is explicit; immutable global config is validated once; operational coupling is intentional and documented. | Follow construction and shutdown end-to-end and compare isolated versus shared failure/test setup. | `runtime_component`, `composition_path`, `lifecycle`, `ambient_dependencies`, `state_scope`, `failure_or_test_cost` |
| `AE-12 Transaction, consistency, and data ownership boundary` | Applicable to multi-aggregate writes, services, databases, caches, events, and distributed workflows. Read data owners, transaction scopes, invariants, event timing, retry/compensation, and consistency requirements. | Map which owner may change each datum and where cross-owner invariants are enforced. Trace commit, event publication, cache update, retries, and partial failure. | Boundary placement permits partial invariant, dual ownership, lost/duplicate publication, unbounded inconsistency, or coordinated deployment for unrelated owners. | Eventual consistency is explicit and bounded; outbox/idempotency/compensation closes the path; the data truly belongs to one transaction owner. | Provide an ordered failure scenario across boundaries and the expected recovery/visibility semantics. | `data_and_owner`, `invariant`, `transaction_scopes`, `publication`, `failure_sequence`, `consistency_result` |
| `AE-13 Evolution and historical trend` | Required for historical comparison and useful when history is cited for any architecture claim. Read committed objects at each endpoint, interval diffs, related tests/config, and identity across renames/moves. | For the same change axis, record concepts, dependency edges, touch set, owners, tests, and pattern role per interval. Classify introduced, eliminated, persistent, or transformed causes. | A trend statement has exact interval and symbol/edge/touch-set evidence showing architecture or extension cost changed. | Only file/LOC counts changed; mechanical rename/move; unrelated features differ; endpoints are not comparable; current worktree contaminated evidence. | Build an interval ledger and identity map; verify each claim against committed objects, not current files. | `interval`, `axis`, `identity_map`, `concepts`, `edges`, `touch_set`, `tests`, `finding_transition` |

## 4. Cross-module and historical passes

For a whole-codebase cross-module scan:

- account for every module in `module_map`;
- account for every public or runtime dependency edge used in conclusions;
- return one disposition for every `AE-01` through `AE-13` ID; `AE-01`,
  `AE-02`, `AE-03`, `AE-04`, `AE-09`, `AE-10`, `AE-11`, and `AE-12` are
  normally applicable and need especially concrete absence evidence if marked
  `not_applicable`;
- trace representative end-to-end paths for each distinct boundary kind, not
  just one path for the repository;
- never infer architecture from directory names alone.

For historical comparison:

- create an independent ledger per interval;
- read committed content from both endpoints;
- preserve rename identity when justified;
- do not copy a finding forward without revalidating its mechanism;
- use `AE-13` to synthesize trends only after interval adjudication.

## 5. Completion and output

Return:

```text
role: Architecture & Evolution
maps_used:
  module_map
  dependency_map
  change_map
  construction_map
  external_boundary_map
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
candidates:
  - Finder candidate records from finding-contract.md
```

An architecture role is incomplete when a required map or check ID is
missing. `not_applicable` needs evidence that its trigger is absent; `blocked`
becomes uncovered. A pattern name never satisfies an evidence field, and
finding no pattern problem is a valid result.
