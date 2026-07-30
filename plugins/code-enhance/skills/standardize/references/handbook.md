# Standardize Finder Handbook

Use this handbook only for the Standardize specialty. Inspect every assigned
review unit against `ST-01` through `ST-08` exactly once. A smell, preferred
syntax, or unmeasured optimization is a search cue, not a candidate.

## Contents

1. Evidence and boundary rules
2. `ST-01` Language idioms
3. `ST-02` Framework and library idioms
4. `ST-03` Algorithmic growth
5. `ST-04` I/O amplification
6. `ST-05` Data structures and allocation
7. `ST-06` Caching and repeated computation
8. `ST-07` Blocking, backpressure, and resource bounds
9. `ST-08` Measurement and regression evidence
10. Coverage ledger

## Evidence and boundary rules

Classify a candidate here only when its smallest effective improvement is a
more idiomatic or more efficient implementation within the existing design
boundary.

For every performance candidate, record:

```text
reachable_workload:
  entry
  trigger_frequency
  scale_variables_and_realistic_values
cost_model:
  current_operation_io_allocation_or_wait_count
  dominant_cost
  proposed_count_and_asymptotic_or_constant-factor_change
measurement:
  benchmark_profile_trace_query_plan_counter_or_operation_count
  environment_and_input
  result_and_limitations
impact:
  latency_throughput_memory_io_capacity_or_user_effect
```

All four sections are mandatory. A reproducible deterministic operation count
may satisfy `measurement` when executing a benchmark is unsafe, but a vague
complexity label may not. Reject a candidate when the workload is unreachable,
strictly bounded below material scale, cold by contract, dominated by another
cost, or unsupported by measurement.

For an idiomatic-writing candidate, record the pinned language/framework
version, the authoritative project or API convention, semantic equivalence
across all callers and error paths, and the concrete cost reduced. Exclude:

- formatter or linter-owned mechanical diagnostics;
- visual arrangement, naming taste, and comment polish (`beautify`);
- deletion of concepts, branches, modes, or layers (`simplify`);
- module ownership, dependency, abstraction, or public-boundary changes
  (`design`);
- attacker-triggered confidentiality, integrity, or availability impact
  (`security`); and
- ordinary correctness, compatibility, or test gaps without a direct
  performance or idiom claim.

## ST-01 Language idioms

**Trigger:** The code manually recreates a construct supplied by the pinned
language/runtime, uses an obsolete form, or obscures standard control,
resource, collection, or error-handling semantics.

**Inspect:** Confirm the pinned version and project conventions. Read the
complete symbol, callers, exceptional paths, ownership/lifetime behavior, and
tests. Compare the current implementation with the native construct.

**Candidate gate:** The native form is available on every supported target,
preserves observable semantics, and demonstrably reduces misuse, maintenance,
or runtime cost. Do not report terseness alone.

## ST-02 Framework and library idioms

**Trigger:** The implementation bypasses a framework/library lifecycle,
bulk/native API, vectorized operation, asynchronous primitive, or documented
fast path and replaces it with custom orchestration.

**Inspect:** Establish exact dependency versions and supported platforms.
Check official/local API contracts, lifecycle requirements, error and
cancellation behavior, call sites, and tests. Look for a project rule that
intentionally rejects the conventional API.

**Candidate gate:** The recommended idiom is supported by pinned versions,
semantically equivalent for this use, and reduces a concrete operating or
maintenance cost. A fashionable API or deprecation guess is insufficient.

## ST-03 Algorithmic growth

**Trigger:** Nested traversal, repeated search/sort, combinatorial expansion,
recursive recomputation, or work whose growth depends on multiple input
dimensions.

**Inspect:** Name every scale variable, derive current operation counts and
bounds, confirm realistic reachable sizes, and identify the actual hot path.
Check short-circuiting, indexes, preprocessing, compiler/runtime behavior, and
existing measurements.

**Candidate gate:** Provide the full performance evidence record and show that
the alternative materially changes asymptotic growth or a measured dominant
constant. Reject textbook complexity concerns at strictly small bounds.

## ST-04 I/O amplification

**Trigger:** A loop or request performs repeated database, network,
filesystem, process, serialization, flush, or synchronization operations that
could plausibly batch or coalesce.

**Inspect:** Count boundary crossings per request/job/item, inspect transaction
and ordering constraints, payload limits, retries, batching already below the
visible layer, query plans, and traces or counters.

**Candidate gate:** Show reachable amplification, measurement, and a
behavior-preserving reduction in crossings. Do not recommend batching when it
breaks latency, atomicity, ordering, memory, rate limits, or failure isolation.

## ST-05 Data structures and allocation

**Trigger:** Membership, lookup, ordering, mutation, copying, conversion,
buffering, or serialization behavior may make the selected representation
materially expensive.

**Inspect:** Derive operation mix, cardinality, lifetime, allocation/copy
count, locality, mutation and ordering guarantees, memory overhead, and
language/runtime optimization behavior.

**Candidate gate:** Measurement and reachable scale show that another
representation reduces dominant time or space cost without weakening required
semantics. Do not replace a small, readable structure on complexity folklore.

## ST-06 Caching and repeated computation

**Trigger:** The same expensive result is recomputed across a demonstrated
reuse window, or an existing cache adds misses, churn, contention, stale data,
or memory growth.

**Inspect:** Measure computation cost, request frequency, key cardinality, hit
rate, lifetime, invalidation source, concurrency, eviction/bounds, ownership,
and failure behavior. Compare no-cache, local reuse, and cache options.

**Candidate gate:** Introduce or change caching only with a measured benefit,
bounded storage, and an evidenced invalidation/lifetime model. Prefer deleting
an ineffective cache when its overhead is measured. Speculative reuse is not
a finding.

## ST-07 Blocking, backpressure, and resource bounds

**Trigger:** Blocking work occupies an event loop or constrained worker;
queues, tasks, buffers, pools, retries, or fan-out lack effective bounds; or
contention limits throughput under normal operational load.

**Inspect:** Reconstruct scheduling and ownership, concurrency limits, queue
arrival/service rates, cancellation, timeouts, retry multiplication, pool
sizes, memory/descriptor/thread bounds, and runtime measurements.

**Candidate gate:** Establish a reachable non-adversarial workload, saturation
or unbounded-growth model, measurement, and material impact. If intentional
untrusted triggering closes a security availability chain, use `security` as
the primary kind.

## ST-08 Measurement and regression evidence

**Trigger:** A performance-sensitive path, claimed optimization, or regression
has benchmark, profile, trace, query-plan, counter, or reproducible workload
evidence that can confirm or falsify its effect.

**Inspect:** Check representativeness, warmup, sample size, variance,
environment, dataset, compiler/build mode, baseline equivalence, units,
confounders, and whether the measured metric corresponds to user or capacity
impact.

**Candidate gate:** Report a faulty optimization or evidence setup only when
it leads to a demonstrated wrong performance decision or leaves a proven
regression unguarded. A missing benchmark by itself is not a finding. Use this
check to disconfirm candidates whose measurements do not survive scrutiny.

## Coverage ledger

Return exactly one inspection record for each `(review_unit, ST-01..ST-08)`
pair:

```text
role: Standardize
review_kind: standardize
check_id: ST-01 | ST-02 | ST-03 | ST-04 | ST-05 | ST-06 | ST-07 | ST-08
status: checked_clear | candidate | not_applicable | blocked
```

Populate every evidence field required by the shared finding contract.
`checked_clear` identifies the performed action and disconfirming evidence.
`not_applicable` identifies the trigger searched for and proof of absence.
Missing, duplicate, unknown, or `blocked` rows make the unit uncovered. Link
every candidate to its originating inspection records and set
`review_kind: standardize`; never assign priority or confidence.
