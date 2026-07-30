# Code Craft Finder Handbook

This handbook is normative for the Code Craft Finder. Its purpose is not to
reward brevity, enforce personal style, or count smells. It tests whether the
code communicates one coherent model with the fewest justified concepts and
supports safe reuse and change.

## Contents

1. Execution order
2. Scope-origin and formatter boundary
3. Mandatory check matrix
4. Craft decision rules
5. Completion and output

## 1. Execution order

For every assigned review unit:

1. Identify its domain terms, responsibilities, state, public contract,
   callers, collaborators, and tests.
2. Reconstruct at least one normal use and one maintenance task from definition
   through call sites and tests.
3. Enumerate `CC-01` through `CC-12` for every review unit and return exactly
   one disposition for each. A `not_applicable` outcome records the trigger,
   artifacts searched, action, and evidence proving absence; never skip a
   check silently.
4. For a suspected problem, state the realistic reader mistake, invalid state,
   synchronized change, navigation burden, or test cost.
5. Search for repository conventions and disconfirming evidence before
   returning a candidate.
6. Return the inspection ledger even when there are no candidates.

## 2. Scope-origin and formatter boundary

- In current-development review, return only craft costs introduced or
  materially worsened by the change. Existing surrounding style is context.
- In historical review, attribute the cost to a specific interval.
- In whole-codebase review, assess the current code.
- Do not duplicate formatter, linter, compiler, or type-checker diagnostics as
  line-by-line craft findings. A distinct semantic cause may still qualify.
- Never use line count, parameter count, cyclomatic-complexity number, or file
  count alone as evidence. Metrics may direct inspection but cannot close it.

## 3. Mandatory check matrix

| Check | Applicability and minimum context | Required inspection | Candidate evidence | Disconfirming evidence | Minimum verification | Ledger payload |
|---|---|---|---|---|---|---|
| `CC-01 Domain language and naming` | Applicable to named symbols, public fields, APIs, errors, tests, and configuration. Read definitions, all relevant in-scope uses, adjacent domain types, requirements, and tests. | Build a small term-to-meaning map. Check one term/one meaning, hidden units or state, misleading verbs, generic placeholders, and inconsistent vocabulary across production and tests. | A concrete plausible misreading or misuse, the name's implied meaning, actual behavior/domain meaning, and resulting maintenance or correctness cost. | The term is an explicit project convention; scope or type removes ambiguity; the distinction is meaningful; rename would conflict with a stable external contract. | Search definitions and uses, compare arguments/returns/state, and identify the exact caller or task that can be misled. | `term`, `declared_or_implied_meaning`, `observed_meanings`, `uses_read`, `misuse_or_delay_scenario` |
| `CC-02 Control flow and local reasoning` | Applicable to executable symbols. Read the complete symbol, state it reads/writes, callees with relevant effects, callers' expectations, and tests. | Enumerate decisions, loops, exits, exceptions, and side effects in execution order. Walk normal, failure, and boundary paths. Identify hidden coupling between branches, temporal dependencies, inverted conditions, and mixed abstraction levels. | A maintainer must remember a non-local condition or side-effect order; a realistic change can update one branch while missing another; or a simpler flow removes a demonstrated reasoning step without hiding behavior. | Complexity is inherent in the domain and mirrors its decision structure; alternatives add dispatch/indirection; guard clauses would separate logic that must be read together. | Perform path walkthroughs and show the current reasoning steps versus the minimal clearer flow. | `decisions`, `exits`, `side_effect_order`, `hidden_dependencies`, `maintenance_task`, `simpler_flow` |
| `CC-03 Responsibility and symbol-level cohesion` | Applicable to functions, classes, modules, components, and test helpers. Read the full unit, owned data, collaborators, call sites, tests, and relevant change history. | List responsibilities, owned invariants, side effects, and reasons to change. Check whether unrelated policy or data ownership is bound together, or whether proposed splitting would sever one invariant. | A concrete change to one responsibility requires understanding/modifying unrelated behavior, or competing owners mutate the same invariant; the minimal move/split reduces that cost. | Responsibilities jointly preserve one domain invariant; they share lifecycle and change together; splitting adds coordination or exposes internals. | Use a real or evidenced change task and list the before/after symbols that must be understood or touched. | `responsibilities`, `owned_data`, `invariants`, `reasons_to_change`, `change_touch_set`, `split_or_move_cost` |
| `CC-04 Concept and indirection economy` | Applicable when a use crosses interfaces, wrappers, factories, registries, base classes, adapters, mappers, configuration, flags, or generic frameworks. Read construction, registration, complete delegation chain, callers, and tests. | Trace a real use case and list every role/type/layer/configuration hop. For each hop, name the policy, invariant, stable boundary, lifecycle, or variation it owns. Compare keeping, collapsing, or inlining it. | A concept contributes no policy/boundary/invariant yet imposes navigation, configuration, debugging, synchronized-edit, or test-fixture cost; removing it preserves needed isolation. | The hop isolates a real external/ownership boundary, centralizes policy, protects an invariant, or absorbs evidenced variation; removing it increases coupling. | Produce a concept ledger and a before/after use-case path. Pattern-related cases also go through `pattern-fit.md`. | `use_case`, `concepts_crossed`, `value_per_concept`, `construction_path`, `navigation_or_config_cost`, `removable_concept` |
| `CC-05 Duplication and honest reuse` | Applicable to similar code, constants, schemas, fixtures, branches, and transformations. Read every suspected site, callers, owners, tests, and relevant history. | Compare semantics, invariant, owner, variation, and change cadence—not only text. Simulate one real change at all sites. Consider data/table extraction, a local helper, shared abstraction, or deliberate duplication. | Sites represent one stable concept, should change together, and currently create divergence or repeated modification; extraction reduces net concepts/touch points without parameter or branch explosion. | Similarity is incidental; owners or change cadence differ; shared code would need mode flags/callbacks; duplication is small and isolates volatile policies. | Search all sites and history where useful; document the shared change and extraction cost. | `sites`, `shared_concept`, `owners`, `change_cadence`, `divergence`, `reuse_option`, `abstraction_cost` |
| `CC-06 Types, invariants, nullability, and ownership` | Applicable to values with constrained states, flags, units, identifiers, nullability, lifetime, mutation, or transfer. Read type definitions, all constructors/parsers, writers, consumers, and tests. | Enumerate valid and invalid states. Trace how a value is created, validated, mutated, transferred, and consumed. Check flag combinations, primitive confusion, unit mixing, partial initialization, and duplicated validation. | A concrete invalid state is constructible/reachable and causes misuse or defensive scattering; a feasible type or centralized constructor prevents it with lower total complexity. | Construction is closed and validated; runtime validation is required at an external boundary; the language cannot express the invariant reasonably; a new type merely relocates checks. | Search all construction and mutation paths and attempt to construct the claimed invalid state statically or through a safe test. | `invariant`, `valid_states`, `invalid_state`, `construction_path`, `enforcement_points`, `type_or_owner_option` |
| `CC-07 API shape and misuse resistance` | Applicable to exported/public/internal shared APIs, constructors, configuration objects, and extension hooks. Read declaration, implementation, all relevant call sites, error semantics, tests, and compatibility constraints. | Check whether the API makes valid use direct and invalid use difficult: argument relationships, defaults, ordering, side effects, lifetime, return/error clarity, discoverability, and unnecessary exposure. | A realistic caller can easily express an invalid combination, misunderstand ownership/lifetime, ignore a necessary result, or depend on internals; a smaller contract prevents the misuse. | Callers are generated/trusted; external compatibility fixes the shape; types/builders already enforce the relation; added ceremony outweighs the rare risk. | Trace representative call sites, including the most complex and failure-prone, and compare the minimal API change. | `api`, `callers_read`, `valid_usage`, `misuse_path`, `contract_leak`, `minimal_shape` |
| `CC-08 Comments, documentation, and intent` | Applicable to comments, docstrings, public contracts, non-obvious algorithms, suppressions, TODOs, and surprising constraints. Read the complete associated code, tests, requirements, and history when the rationale is historical. | Classify each material statement as contract, invariant, rationale, tradeoff, workaround, or syntax narration. Verify it against current code and source of truth. Identify non-obvious constraints that cannot be discovered safely from types/code. | A statement is stale or contradicts behavior; critical intent/invariant is absent and causes a plausible unsafe edit or misuse; suppression/workaround no longer matches its cause. | Code/types/tests express the fact clearly; comment intentionally preserves external rationale; missing prose is already in the authoritative project documentation. | Compare each claim with implementation and tests; consult history only to establish durable rationale, not to preserve obsolete code. | `statement_or_missing_intent`, `kind`, `source_of_truth`, `match`, `maintenance_impact` |
| `CC-09 Data flow, mutation, and side-effect visibility` | Applicable to mutable structures, implicit globals/context, callbacks, lazy values, caches, and functions with effects. Read producers, aliases, mutation sites, consumers, and tests. | Trace ownership and mutation order. Check surprising mutation through aliases, temporal coupling, hidden I/O, functions whose names/types conceal effects, and scattered state synchronization. | A caller can reasonably assume purity/ownership and be wrong; a change depends on undocumented sequencing; hidden effects force broad setup or cause stale/inconsistent data. | Mutation is local and idiomatic; ownership is explicit; lifecycle requires shared state and is encapsulated; copying would be more costly or incorrect. | Follow at least one end-to-end value path and all relevant writes; identify the concrete caller or test burden. | `value_or_state`, `owner`, `aliases`, `writes`, `consumers`, `hidden_effect`, `clarifying_option` |
| `CC-10 Test craft and diagnostic value` | Applicable to tests, fixtures, factories, mocks, snapshots, and helpers. Read the test end-to-end, production seam, setup helpers, assertions, and CI behavior. | Trace setup → trigger → observation. Check domain readability, irrelevant setup, shared mutable fixtures, time/random/network nondeterminism, implementation coupling, assertion depth, and failure localization. | A realistic production refactor breaks many behavior-preserving tests; a test can pass without observing the behavior; nondeterminism is reachable; or failure output cannot identify the violated contract. | Integration-level setup is required; snapshot is the contract; fixture expresses stable domain language; project harness controls time/randomness; higher-level oracle is intentional. | Run the narrowest test when safe, inspect assertion and failure signal, and compare how a behavior-preserving change propagates. | `test`, `behavior`, `setup_dependencies`, `seam`, `oracle`, `nondeterminism`, `maintenance_cost` |
| `CC-11 Dead paths, obsolete compatibility, and speculative generality` | Applicable to unused branches, flags, deprecated adapters, unreferenced exports, commented code, generic hooks, and "future" parameters. Read references, runtime registration/reflection, compatibility docs, tests, and history. | Establish reachability and ownership. Determine whether the path serves runtime discovery, external consumers, staged migration, rollback, or a real planned variant. Measure its concept and synchronization cost. | Code is unreachable/unused under supported configurations or an extension point represents no real variation, while retaining it creates current navigation, testing, or modification burden. | Dynamic/reflection use exists; public compatibility requires it; migration/rollback window is active; the seam isolates a real boundary; removal risk cannot be established. | Use repository-aware reference search plus config/registration/history. If external use cannot be ruled out, reject or mark blocked—not dead. | `symbol_or_path`, `references_checked`, `dynamic_use`, `compatibility_basis`, `current_cost`, `removal_risk` |
| `CC-12 Language and project idiom with semantic impact` | Applicable when code diverges from a project-established idiom in a way a formatter/linter cannot decide. Read applicable rules, pinned language/framework version, nearby canonical code, and tests. | Determine why the idiom exists: safety, lifecycle, ownership, interoperability, diagnostics, or maintainability. Compare semantics, not fashion or modernity. | The divergence causes a concrete misuse, inconsistent contract, hidden lifecycle, or maintenance burden under this project's conventions. | Difference is stylistic; project supports both; newer syntax changes compatibility; local code is clearer; a linter already owns the rule. | Cite the exact project rule or semantic behavior and the affected caller/task. Do not rely on generic "best practice." | `idiom`, `project_basis`, `version_basis`, `semantic_difference`, `affected_use`, `mechanical_tool_boundary` |

## 4. Craft decision rules

Apply these rules across the matrix:

- **Clarity:** Count the concepts and context switches required for a realistic
  task, not the number of lines.
- **Small functions:** A function is too large only when responsibilities,
  abstraction levels, or hidden path coupling create a demonstrated cost.
- **DRY:** Knowledge should have one owner; visually similar code may be
  deliberately separate.
- **Reuse:** Prefer reuse after a stable common concept is established. Do not
  create a shared abstraction merely to remove repeated syntax.
- **Types:** Strengthen types when they eliminate a reachable invalid state.
  Avoid wrapper types that only rename a primitive without enforcing meaning.
- **Comments:** Preserve "why," invariants, and external constraints. Do not
  request comments that narrate readable syntax.
- **Simplification:** State which concept, branch, configuration, or navigation
  hop disappears and verify the same behavior remains expressible.
- **Praise is not coverage:** Positive observations may be returned as
  disconfirming evidence, but do not replace check records with a strengths
  section.

The Code Craft Finder does not recommend named design patterns. If a craft
problem may require an architectural abstraction, describe the proven local
cost and leave pattern selection to Architecture & Evolution and validation.

## 5. Completion and output

Return:

```text
role: Code Craft
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

`checked_clear` must name the inspection performed and the evidence that
defeated or failed to support a candidate. `not_applicable` requires the
trigger evaluated, exact artifacts searched, action, and evidence proving
absence. `blocked` makes that review unit uncovered. Complete all checks after
finding an issue; there is no quota in either direction.
