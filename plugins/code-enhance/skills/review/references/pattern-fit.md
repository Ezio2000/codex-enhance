# Pattern Fitness and YAGNI Challenge

Good architecture localizes change while minimizing coupling, concepts, and
test cost. A design-pattern name is useful only after the code demonstrates a
problem shape that the pattern improves.

## Contents

1. Pattern admission gate
2. Action-specific gate routing
3. Mandatory three-option comparison
4. OCP interpretation
5. Shape is not evidence
6. Pattern decision cards
7. Removing patterns
8. Historical evidence
9. Accepted and rejected wording

## Pattern admission gate

Recommend introducing or expanding a design pattern only when all five
conditions hold:

1. **Current pain exists.** The code has a demonstrated correctness,
   maintenance, coupling, testing, or extension cost.
2. **The variation or invariant axis is real.** There are multiple genuine
   variants, a stable external boundary, historical evidence of repeated
   change along the same axis, or a construction/lifecycle axis with distinct
   legal stages or reachable invalid constructions. A simple constructor with
   independent parameters does not satisfy this gate.
3. **Modification spread shrinks.** The proposal measurably reduces the files,
   modules, conditionals, callers, construction checks, or tests touched by
   the evidenced change or invariant-preserving construction change.
4. **A simpler option is insufficient.** Renaming, extracting a function,
   moving ownership, strengthening a type, or using data instead of control
   flow cannot solve the problem as effectively.
5. **Net complexity falls.** Coupling, concept count, cognitive load, or test
   cost decreases after accounting for the new types, indirection, lifecycle,
   configuration, and failure modes.

If any condition fails, the pattern judgment is **暂不引入模式** in Chinese
reports or its direct equivalent in the user's language.

For this gate, distinct legal construction or lifecycle stages are genuine
state variants only when the current design permits a concrete invalid
construction or duplicates invariant-preserving changes. Optional parameters
or an imagined future build sequence do not qualify.

Record the gate; do not merely claim it passed:

```text
current_pain:
  pass_or_fail
  evidence
real_variation_boundary_or_construction_lifecycle_axis:
  pass_or_fail
  variants, boundary, history, legal stages, or reachable invalid construction
  same_evidenced_axis
modification_spread_shrinks:
  pass_or_fail
  before_touch_set
  after_touch_set
simpler_option_insufficient:
  pass_or_fail
  options_tried
net_complexity_falls:
  pass_or_fail
  concepts_dependencies_configuration_failure_modes_tests_before_and_after
participant_semantic_fit:
  proposed_roles
  why_each_role_matches_the_same_evidenced_axis
plausible_named_alternatives:
  alternative
  why_rejected
```

All five entries require code, contract, test, or history evidence. A pattern
name, implementation count, repeated syntax, or generic SOLID statement is not
evidence for a gate.

`same_evidenced_axis` prevents an unrelated external boundary or historical
change from satisfying the variation gate. `participant_semantic_fit` is not
an extra admission gate; it proves that the proposed pattern actually
addresses the pain tested by the five gates. When another named pattern is
clearly plausible, compare it briefly rather than choosing by familiarity.

## Action-specific gate routing

First record:

```text
pattern_action:
  none | keep | introduce | expand | remove | collapse | replace | disputed
underlying_problem_verdict:
  Confirmed | Supported | Rejected
pattern_judgment:
  keep | introduce | expand | remove | collapse | replace | defer | not_relevant
```

Then apply the gate appropriate to the action:

- `introduce` or `expand`: all five admission gates above.
- `remove` or `collapse`: all five removal gates in **Removing patterns**.
- `replace`: removal gates for the existing pattern and admission gates for
  the replacement.
- `keep`: retention evidence and the counterfactual-removal check below.
- `disputed`: evaluate every concrete action still under consideration.

The underlying problem and the named-pattern judgment are separate. A proven
maintenance problem may remain `Confirmed` or `Supported` while a Strategy,
Factory, or other proposal is `defer`; recommend the validated minimal
improvement instead. If the only claim is "a pattern is missing," failure of
any admission gate rejects that claim.

For `keep`, record:

```text
represented_variation_boundary_or_policy
participant_semantic_fit
current_overhead
counterfactual_removal_touch_set_and_lost_isolation
retention_judgment
```

Keeping does not require inventing current pain. It requires evidence that the
pattern represents something real and that removal would lose useful
isolation, policy, invariant enforcement, lifecycle control, or change
locality at proportionate overhead.

## Mandatory three-option comparison

Every disputed abstraction, interface, extension point, or pattern proposal
must compare:

### Keep the current design

Record:

- current modification surface;
- current concepts and dependencies;
- present failure or maintenance cost;
- whether the pain is recurring or one-off.

### Apply a minimal refactor

Consider, as appropriate:

- rename or relocate ownership;
- extract a small function or value object;
- replace conditionals with a table or data;
- consolidate truly shared logic;
- make an invariant explicit in a type;
- isolate one external boundary;
- delete pass-through layers.

Record which proven cost disappears and what remains.

### Use a patternized design

Record:

- new roles, types, configuration, and indirection;
- which real variants or boundary it represents;
- exact change surface before and after;
- test-seam improvement;
- migration and misuse risk;
- why the minimal refactor is not enough.

Choose the option with the lowest total cost that solves the evidenced
problem. Do not choose the most extensible option in the abstract.

Use this comparison record:

```text
option
behavior_and_boundaries_preserved
symbols_files_and_tests_touched_for_the_real_change
concepts_and_roles
dependency_edges
construction_and_configuration
failure_modes_and_lifecycle
test_seams_and_fixture_cost
migration_and_compatibility_cost
unresolved_proven_pain
```

The purpose is a concrete surface comparison, not a numeric architecture
score. Count only when counts help identify exact touch points; no universal
threshold decides the result.

## OCP interpretation

The open-closed principle does not require every class to be extensible. It
means code should be open along evidenced variation axes and closed against
unrelated modification.

Support an OCP finding only when:

- the same kind of variant repeatedly forces edits to stable code;
- a new case changes scattered conditionals or unrelated modules;
- a stable external protocol or platform boundary needs isolation;
- change history shows a recurring axis;
- testing one variant requires constructing or executing unrelated variants.

Reject an OCP finding when:

- the domain has one stable case;
- the expected change is speculative;
- a local conditional is clearer and cheaper;
- an extension point would expose unstable internals;
- the proposed abstraction merely relocates the same switch.

## Shape is not evidence

### Single-implementation interface

Do not remove or criticize it solely for having one implementation. It may
express a stable external boundary, ownership boundary, compatibility
contract, dependency inversion seam, or test seam. Keep it when the boundary
is real and its contract is smaller and more stable than the implementation.

Challenge it when it merely renames the concrete class, leaks every
implementation detail, exists only for mocking, or expands navigation and
configuration without isolating change.

### One-product Factory

Do not criticize it solely because it creates one product. It may centralize
construction policy, lifecycle, platform selection, compatibility, or
expensive setup.

Challenge it when it is only a synonym for a constructor, owns no policy, and
there is no evidenced second construction path or stable creation boundary.

### Pass-through Wrapper

Do not criticize delegation alone. A wrapper may enforce authorization,
validation, observability, compatibility, resource lifetime, retries, or a
stable facade.

Challenge it when every method mirrors another object, contributes no policy
or invariant, and forces coordinated edits for no reduction in coupling.

### Repeated switch

A repeated switch is evidence only when its branches represent the same
variation axis and repeatedly change together. Before recommending Strategy,
polymorphism, visitors, handlers, or registries, check whether:

- a lookup table or extracted function is enough;
- the cases need independent ownership or testing;
- new cases are actually recurring;
- distributing behavior improves locality instead of hiding the full set.

### Adapter

One implementation of an Adapter is often appropriate when it isolates an
external API, platform, storage engine, wire format, or unstable vendor
contract. Judge the stability and direction of the boundary, not implementation
count.

## Pattern decision cards

These cards constrain common pattern suggestions. They are not a catalog that
must be applied. First prove the pain and variation; then use the relevant
card.

| Pattern or shape | Evidence that can justify it | Evidence that defeats or limits it | Simpler options to test first |
|---|---|---|---|
| **Adapter** | A stable local contract must translate an incompatible or volatile external API, protocol, platform, storage engine, or wire format; callers and tests benefit from not knowing vendor details. One implementation is sufficient. | Input/output and failure semantics are merely forwarded; vendor types still leak through; no local policy or translation exists; replacing it touches the same callers. | One boundary function, local mapper, or direct standard-library call when the surface is tiny and stable. |
| **Strategy** | Multiple genuine algorithms implement the same stable operation, are selected independently, and change/test independently; same-axis branching is scattered or recurring. | Only one real algorithm exists; selection is a local exhaustive conditional; strategies need mode flags or share most branches; distributed classes hide the full rule set. | Lookup table, data-driven rule, extracted function, or one local conditional. |
| **State** | States own distinct legal transitions, behavior, and invariants; transition logic is scattered and invalid transitions are currently reachable. | An enum only selects display text/data; transitions are few and clear in one state machine/table; objects require cross-casting or duplicate shared logic. | Explicit transition table, validated enum/value object, or centralized state function. |
| **Factory** | Construction owns product-family selection, lifecycle, compatibility, expensive setup, dependency assembly, or runtime platform policy. One current product may still be justified by a stable creation boundary. | It only renames a constructor, returns one concrete object, owns no policy, and adds registration/configuration for no current boundary. | Constructor, named constructor, small composition-root function. |
| **Builder** | Construction is staged, has meaningful optional groups, multiple representations, ordering constraints, or invariants that a constructor cannot express clearly. | There are a few independent parameters, no invalid combinations, and builder steps only assign fields; required values can be omitted until runtime. | Parameter object with validation, named constructor, defaults, or direct immutable construction. |
| **Command** | Operations must be queued, retried, logged/audited, authorized uniformly, delayed, composed, or undone as values with a stable execution contract. | A single synchronous call is wrapped as an object; no lifecycle or cross-cutting policy exists; callers must navigate more types for the same call. | Function/closure, handler method, or explicit job payload at the actual queue boundary. |
| **Observer or event** | Multiple independent consumers react to one event, ownership/lifecycle decoupling is real, and delivery/order/error semantics are defined and tested. | One synchronous consumer exists; hidden control flow makes failures/order harder to trace; events duplicate direct commands; delivery semantics are unspecified. | Direct call, explicit callback, returned result, or orchestrator-owned sequence. |
| **Decorator** | Several orthogonal behaviors apply to a stable contract in varying combinations and order; composition reduces subclass/branch growth. | Only one wrapper layer exists; behavior is not independently composable; order/identity semantics become surprising; every method is pure pass-through. | Direct policy call, helper, explicit pipeline, or one named wrapper with real boundary semantics. |
| **Proxy** | Access control, remote access, lazy loading, caching, lifecycle, or expensive-resource ownership must preserve a stable subject contract. | Proxy hides I/O or latency behind an apparently local call, breaks identity/equality, or adds no access/lifecycle policy. | Explicit gateway/client/cache or a method whose name exposes the effect. |
| **Facade** | A genuinely complex subsystem has many coordination steps and callers need one smaller, stable use-case boundary. | It only renames and forwards one service; it mirrors the subsystem surface; callers still depend on internals; coordinated behavior belongs to a domain owner elsewhere. | Use-case function, module export boundary, or relocating orchestration to the owning service. |
| **Repository** | Domain use cases need a stable persistence contract distinct from ORM/vendor representation, multiple stores or complex query semantics exist, or a real test/boundary benefit is demonstrated. | It is CRUD-for-CRUD passthrough over one ORM, leaks ORM query/types, duplicates capabilities, or encourages unrealistic in-memory substitutes. | Direct data access in the infrastructure/application boundary, focused query object, or transaction-scoped gateway. |
| **Template Method or base class** | A stable algorithm skeleton exists, variation points are constrained, substitutability is real, and lifecycle ordering must be enforced centrally. | Subclasses override many hooks, depend on base internals, require flags/type checks, or inherit only for reuse; variants need independent composition. | Functions, composition/delegation, explicit pipeline, or shared helper. |
| **Dependency injection boundary** | Real external dependencies, runtime variants, lifecycle, or failure simulation require explicit construction and replacement; dependencies become visible at the composition root. | A container/service locator hides dependencies, every class gains interfaces with no boundary, or tests mock internal details rather than behavior. | Constructor/function parameters for concrete stable types, one composition-root function, or direct creation for local pure objects. |
| **CQRS, event sourcing, saga, or other system-level pattern** | Independent read/write scaling or models, authoritative audit/time-travel, distributed transaction/compensation, or regulatory recovery requirements already exist and simpler transactional designs are inadequate. | Suggested for abstract scalability; consistency, ordering, schema evolution, replay, operations, and failure modes are unspecified; one service/database already meets requirements. | Transaction plus outbox, audit log, materialized query, explicit workflow, or localized async job. |

For any card, also inspect the failure semantics introduced by the pattern.
An event bus, proxy, cache, registry, or container can reduce one change surface
while adding ordering, lifecycle, configuration, or observability failures.
Those costs belong in the gate record.

## Removing patterns

Removal must pass the same rigor as introduction. Recommend removing or
collapsing a pattern only when:

- its represented need no longer exists, never existed, is obsolete, or is not
  actually served by the current participants;
- indirection or semantic misuse creates a demonstrated navigation,
  configuration, debugging, change, failure, or test cost;
- no required boundary, policy, invariant, or lifecycle is lost, or a
  replacement improves how it is represented;
- a smaller or replacement design reduces net complexity while preserving
  behavior and required isolation;
- migration risk is proportionate to the benefit.

Do not flatten a valid external boundary merely to reduce file count.

Record removal/collapse gates explicitly:

```text
represented_need_absent_obsolete_or_not_served_by_participants:
  pass_or_fail
  evidence
demonstrated_indirection_or_misuse_cost:
  pass_or_fail
  navigation_configuration_debugging_change_failure_test_or_edit_cost
no_required_boundary_is_lost_or_replacement_improves_it:
  pass_or_fail
  boundary_policy_invariant_and_lifecycle_evidence
smaller_or_replacement_design_reduces_net_complexity:
  pass_or_fail
  counterfactual_design_touch_set_and_preserved_isolation
migration_risk_is_proportionate:
  pass_or_fail
  compatibility_rollout_and_failure_cost
```

For `replace`, complete this record for the existing pattern and the admission
record for the replacement. Passing only one side is insufficient.

## Historical evidence

For version comparisons, use history to ask:

- Did new variants extend an existing seam or edit stable core logic?
- Did an abstraction reduce or increase touched modules?
- Did concept count rise while extension cost stayed the same?
- Did a pattern absorb repeated change or merely move it?
- Did tests become more focused, or require more scaffolding?

Classify patterns as appropriate, missing, misused, overused, removed, or not
yet justified only after this evidence is traced.

## Accepted and rejected wording

An accepted finding describes the pain before the pattern:

> Adding a payment provider requires edits in three stable modules and repeats
> the same branching in production and tests; centralizing provider behavior
> behind the existing boundary would reduce that modification surface.

Avoid name-first claims:

> This code should use Strategy.

When a pattern is not justified, record the decision in the rejected-opinions
table only if the proposal was genuinely disputed. State the observed evidence,
the missing admission condition, and the simpler decision. Do not turn that
rejection into a formal finding.
