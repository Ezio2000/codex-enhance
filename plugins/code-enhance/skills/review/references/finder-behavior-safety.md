# Behavior & Safety Finder Handbook

This handbook is normative for the Behavior & Safety Finder. It turns the
role into auditable inspection work. Reading a diff, file header, test name,
or summary is not enough to complete any check.

## Contents

1. Execution order
2. Scope-origin rule
3. Mandatory check matrix
4. Surface-triggered supplements
5. Completion and output

## 1. Execution order

For every assigned review unit:

1. Inventory its externally reachable entry points, inputs, outputs, state,
   side effects, trust crossings, resources, and behavior tests.
2. Enumerate `BS-01` through `BS-12` for every review unit and return exactly
   one disposition for each. For `not_applicable`, record the trigger checked,
   artifacts searched, action, and evidence proving absence; never omit a
   check silently.
3. Trace each applicable behavior from an entry or caller guarantee through
   transformations and guards to its result or side-effect boundary.
4. Inspect the normal path, at least one failure path, and every materially
   different boundary or state transition visible in the code.
5. Search for disconfirming evidence before creating a candidate.
6. Return both the inspection ledger and any candidates. Zero candidates is
   valid only when the ledger closes.

Use project-defined contracts and supported environments as the oracle. Do
not impose a generic behavior that conflicts with repository rules.

## 2. Scope-origin rule

Attribute the issue before returning it:

- For current-development review, the change must introduce, expose, or
  materially worsen the problem. A pre-existing problem is context, not a
  candidate, unless the changed code now depends on it in a newly unsafe way.
- For a historical interval, identify the first reviewed interval in which
  the problem becomes present or materially changes.
- For whole-codebase review, review the current implementation without an
  introduction requirement.

Record `scope_origin` with a changed hunk, committed object, or current symbol.
Do not infer origin from file modification time or proximity alone.

## 3. Mandatory check matrix

| Check | Applicability and minimum context | Required inspection | Candidate evidence | Disconfirming evidence | Minimum verification | Ledger payload |
|---|---|---|---|---|---|---|
| `BS-01 Contract and observable result` | Applicable to every callable entry, job, handler, command, hook, exported API, and changed behavior. Read the complete enclosing symbol, applicable requirements/types/docs, direct in-scope callers, downstream side-effect boundary, and related tests. | Extract preconditions, postconditions, invariants, and failure semantics. Trace every materially distinct return/exit from input to observable result. Compare documented and de-facto caller expectations. When a plan, ticket, or acceptance criteria is available, account for every item as met, partially met, not met, or not assessable and check missing, extra, and misunderstood behavior. | A reachable input/state or requirement item, an authoritative or established contract, the complete control/data path, and the exact expected-versus-actual consequence. Extra implementation qualifies only when it creates a proven compatibility, safety, or maintenance cost. | Caller or schema proves the precondition; a guard dominates the path; normalization occurs earlier; the alleged result is the intended contract; a test demonstrates the opposite behavior; or the supposed extra behavior is a justified implementation detail with no cost. | Run the narrowest existing behavior/contract test or a safe read-only reproduction. If execution is impossible, provide an unbroken static trace and the reason execution was unavailable. | `entrypoint_or_requirement`, `contract_source`, `requirement_status`, `preconditions`, `trace`, `expected`, `actual`, `scope_origin` |
| `BS-02 Input boundary, parsing, and round trip` | Applicable where data enters, is parsed, normalized, validated, converted, or serialized. Read schemas/types, parser, normalizer, serializer, caller, fixtures, and consumer. | Build relevant input classes: missing, null, empty, zero, negative, extreme, duplicate, unordered, malformed, encoded, locale/time-zone/precision variants, and partial data. Trace accepted classes through conversions and round trips. For a new enum/discriminator case, enumerate every producer, storage form, parser, filter, branch, serializer, and presentation consumer. | A permitted or realistically reachable class causes ambiguity, truncation, overflow, precision loss, encoding error, inconsistent normalization, unsafe fallback, unhandled consumer, or wrong output. | Schema/caller excludes the class; conversion is lossless for the supported domain; every consumer handles or deliberately rejects it; round trip preserves semantics; explicit rejection is the contract. | Execute a focused boundary or round-trip test when safe; otherwise show exact accepted-by, transformed-by, and consumed-by steps. | `input_class`, `accepted_by`, `transforms`, `consumers_enumerated`, `round_trip`, `oracle`, `outcome` |
| `BS-03 State transition, idempotency, and partial failure` | Applicable to mutable state, workflows, persistence, caches, retries, commands, and multi-step side effects. Read the state owner, every relevant write, transaction/compensation boundary, retry caller, and tests. | Enumerate legal states and transitions. Walk success, repeated invocation, interruption, partial success, retry, and rollback/compensation paths. Check when external effects become visible. | A concrete event sequence reaches an illegal state, duplicates or loses an effect, commits only part of an invariant, cannot resume safely, or violates idempotency promised by the contract. | Transactionality, compare-and-set, idempotency key, deduplication, compensation, or state ownership covers every exit and repetition. | Run a state-sequence or failure-injection test when present; otherwise record the ordered events, writes, exits, and final state. | `state_before`, `event_sequence`, `writes`, `visibility_point`, `recovery`, `state_after` |
| `BS-04 Error propagation, retry, recovery, and observability` | Applicable to fallible calls and explicit error channels. Read the complete error-producing and error-consuming chain, retry policy, cleanup, user/API mapping, and relevant logs/metrics/tests. | First enumerate catches, error callbacks/results, failure branches, fallbacks/defaults, log-and-continue paths, error-masking null handling, and retry exhaustion. Then trace each distinct error class through those boundaries. Check preservation of cause, retryability, user-visible contract, cleanup, and diagnostic signal. | An error is swallowed, misclassified, retried unsafely, converted to success, leaks an internal detail, loses actionable context, or leaves state/resources inconsistent. | Deliberate best-effort semantics are documented; error mapping is stable and tested; retry policy is bounded and idempotent; higher layer adds the required context. Logging or user notification is required only by the actual contract, not universally. | Trigger or run the narrowest error-path test. If not executable, give the exact producer-to-consumer path and mapping at each boundary. | `error_sites_enumerated`, `error_source`, `error_class`, `mapping_chain`, `retry_policy`, `observable_result`, `diagnostic_signal` |
| `BS-05 Compatibility, schema, configuration, and migration` | Applicable to public APIs, persisted data, messages, config, CLI syntax, plugin surfaces, deployment artifacts, and supported platform/version changes. Read old and new contracts, all in-scope callers/consumers, defaults, migrations, and compatibility tests. | Build the supported-case matrix. Compare additions, removals, renames, defaults, encoding, ordering, and semantic changes. Trace upgrade, downgrade, mixed-version, and rollback paths when the project supports them. | A supported consumer/version/platform cannot read, invoke, migrate, roll back, or preserve prior semantics; or a default silently changes behavior. | Breaking change is explicitly versioned and all consumers migrate atomically; compatibility layer covers the case; migration is reversible where required; support was explicitly dropped. | Run contract/compatibility/migration checks when available; otherwise compare exact serialized/API surfaces and consumer assumptions. | `supported_case`, `old_contract`, `new_contract`, `consumer`, `migration_or_shim`, `compatibility_result` |
| `BS-06 Resource lifetime, cancellation, and cleanup` | Applicable to files, sockets, streams, processes, locks, transactions, subscriptions, timers, tasks, memory ownership, and temporary resources. Read acquisition, transfer, all exits, cancellation, shutdown, and cleanup code. | Pair every acquisition with ownership and release. Trace success, exception, early return, timeout, cancellation, shutdown, and repeated close. Check use-after-close and cleanup ordering. | A reachable exit leaks, double-releases, uses after release, leaves a child task/process alive, blocks shutdown, or cleans up in an unsafe order. | RAII/context manager/finally/defer owns every exit; ownership transfers exactly once; cancellation is propagated and awaited; release is idempotent. | Run an existing lifecycle/cancellation test or supply an exit-by-exit pairing table. | `resource`, `acquired_at`, `owner`, `transfer`, `exit_paths`, `released_at`, `cancellation_path` |
| `BS-07 Concurrency, ordering, and atomicity` | Applicable when more than one thread, task, callback, process, request, event, or actor can touch related state. Read every relevant read/write, scheduler boundary, synchronization primitive, lock order, transaction, and cancellation path. | Identify shared mutable state and actors. Construct concrete interleavings around read-modify-write, publication, initialization, teardown, callbacks, retries, and awaits. Verify ordering and atomicity assumptions. | A feasible interleaving causes lost update, stale read, duplicate effect, race, deadlock, starvation, inconsistent publication, shutdown race, or cancellation leak. | State is immutable/thread-local/actor-owned; execution is provably serialized; atomic operation spans the invariant; lock order is uniform; duplicate work is harmless by contract. | Run targeted concurrency/race tests if available; otherwise provide a timestamped actor interleaving and the missing guarantee. | `shared_state`, `actors`, `accesses`, `synchronization`, `interleaving`, `bad_outcome` |
| `BS-08 Authentication, authorization, and trust boundary` | Applicable to identity establishment, privileged operations, tenant/user/resource access, admin paths, callbacks, and cross-service boundaries. Read ingress, identity derivation, authorization policy, object lookup, privileged sink, and deployment assumptions. | Establish the attacker or untrusted caller. Trace identity and resource identifiers across trust boundaries. Check authorization at the operation and object level, tenant binding, confused-deputy paths, and default-deny behavior. | Attacker capability, entry, controllable value, missing/bypassable control, protected operation/data, and impact are all explicit. | An unforgeable identity is bound to the resource; authorization dominates every sink; intermediary cannot widen authority; deployment boundary truly prevents access. | Run a focused authorization-negative test when safe; otherwise provide the complete identity/resource/control/sink trace. | `attacker`, `entry`, `identity`, `resource`, `trust_crossings`, `controls`, `privileged_sink`, `impact` |
| `BS-09 Injection, unsafe interpretation, and path handling` | Applicable where untrusted data reaches SQL/query languages, templates/HTML, shells/processes, file paths, URLs, redirects, deserializers, regexes, code loaders, or configuration interpreters. Read the source, every transform/validation, and final interpreter. | Perform a source-to-sink trace. Check context-specific encoding or parameterization, allow-list semantics, canonicalization order, parser differentials, and whether validation occurs before the final interpretation. | A controllable value reaches an interpreter in a dangerous context with a missing or bypassable control and a concrete payload class or escape mechanism. | Bound parameters, context-correct encoding, typed APIs, post-canonicalization allow-list, safe parser configuration, or non-attacker-controlled source cuts the path. | Use a safe existing security test or static taint trace; do not execute destructive payloads. | `source`, `transforms`, `validation`, `canonicalization`, `sink`, `payload_class`, `impact` |
| `BS-10 Secrets, privacy, and sensitive-data lifecycle` | Applicable to credentials, tokens, personal/sensitive data, logs, telemetry, caches, storage, exports, and error messages. Read collection, access, transport, storage, logging, retention/deletion, and configuration. | Classify sensitive fields. Trace who can provide, read, emit, persist, log, cache, and delete them. Check least privilege, redaction, accidental copies, retention, and failure paths. | Sensitive material is exposed to an unauthorized actor or channel, retained contrary to contract, logged or cached without protection, or accepted from an unsafe source. | Data is non-sensitive by project definition; redaction occurs before every output; access boundary and storage protection are explicit; retention is required and bounded. | Inspect exact output/log/storage paths and relevant tests/configuration; never print or retrieve live secret values. | `data_class`, `source`, `readers`, `outputs`, `storage`, `redaction`, `retention`, `impact` |
| `BS-11 Performance, I/O amplification, and resource bounds` | Applicable to loops over variable input, queries, network/storage calls, allocations, caches, queues, recursion, blocking operations, and hot request/job paths. Read the complete path, scale source, storage/network API, bounds, and benchmarks/operational clues. | Name scale variables and derive operation, allocation, and I/O counts. Check N+1 patterns, repeated scans, blocking in async paths, unbounded accumulation, fan-out, cache lifecycle, and backpressure. Establish realistic reachability. | A cost expression, I/O amplification, blocking path, missing bound, resource exhaustion path, or measurement is tied to a reachable workload and impact. | Strict small bound, cold/admin path, batching/index/cache already limits cost, backpressure exists, or measurement disproves the concern. | Prefer benchmark/profile/query-plan evidence. Otherwise provide the cost model, reachable scale, bound analysis, and limitation. | `size_variables`, `operation_count`, `io_count`, `allocation_or_queue`, `bounds`, `hot_path_evidence`, `measurement` |
| `BS-12 Behavioral test effectiveness` | Applicable to every risk or contract identified above and every changed behavior. Read production path, unit/integration/contract/e2e tests, fixtures/mocks, and CI selection. | Map each material behavior and failure path to a test that reaches it and observes the outcome. Check meaningful oracle, negative/boundary paths, integration seams, determinism, and whether mocks preserve the contract. | A demonstrated risky path lacks an effective oracle, a test never reaches the claimed branch, a mock makes the failure impossible, or a passing assertion observes only setup/implementation detail. | A higher-level stable test covers the same path; static/type guarantee makes it unreachable; the alleged risk was falsified; project explicitly tests it elsewhere. | Run the narrowest related test and inspect its assertion/failure signal, not only coverage or test name. | `risk_or_contract`, `tests_searched`, `test`, `branch_reached`, `oracle`, `gap_consequence` |

## 4. Surface-triggered supplements

Apply these only when the assigned unit exposes the surface. They do not
replace the matrix above.

| Supplement check | Surface | Additional mandatory questions |
|---|---|---|
| `BS-S01` | HTTP/RPC/API | Method and route semantics; content-type and parsing; authentication before body-dependent work; object-level authorization; pagination and limits; idempotency; timeout/cancellation; error/status compatibility; request/response data exposure. |
| `BS-S02` | Persistence and migrations | Transaction boundary; constraints and invariants; query cardinality; N+1 and index assumptions; partial migration; mixed-version readers/writers; rollback; destructive conversion; concurrency and isolation. |
| `BS-S03` | Queues, events, and jobs | Delivery guarantee; duplicate and out-of-order handling; poison messages; retry/backoff bound; idempotency; acknowledgement timing; dead-letter behavior; schema evolution; shutdown ownership. |
| `BS-S04` | Filesystem, URL, and process execution | Canonicalization; root confinement; symlink/race behavior; argument separation; environment inheritance; timeout; child cleanup; output bounds; trust of downloaded or parsed content. |
| `BS-S05` | UI or client state | Stale async results; duplicate submission; loading/error/empty states; state ownership; cancellation/unmount; unsafe rendering; sensitive client storage; backend contract mismatch. |
| `BS-S06` | CLI and configuration | Backward-compatible flags/config keys; precedence; invalid/missing values; secret handling; exit status; partial output; non-interactive behavior; platform paths and quoting. |
| `BS-S07` | Infrastructure and CI | Privilege scope; secret exposure; untrusted-code execution; mutable tags; artifact provenance; deployment ordering; rollback; concurrency; environment drift; destructive defaults. |

For every surface exposed by `surface_inventory`, return one evidenced
disposition for its `BS-S*` ID in every review unit that contains or crosses
that surface. Do not emit supplements for absent surfaces, but the main agent
must reconcile the selected supplement-ID set with `surface_inventory`.

When a claim depends on a language, framework, database, or protocol version,
read the repository's pinned version and authoritative local documentation or
configuration. If the semantics cannot be established, mark the check
`blocked`; do not rely on a remembered best practice as proof.

## 5. Completion and output

Return:

```text
role: Behavior & Safety
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

Rules:

- `checked_clear` requires an executed inspection action plus the strongest
  relevant disconfirming evidence; "looked okay" is invalid.
- `candidate` requires one or more candidate IDs and the evidence gate in the
  matrix.
- `not_applicable` requires the applicability trigger, exact artifacts
  searched, inspection action, and evidence proving absence.
- `blocked` names the exact missing object, context, semantic fact, or safe
  verification. It makes the affected unit uncovered.
- Do not stop after the first issue. Complete every applicable check for every
  assigned review unit.
- Do not manufacture an issue to demonstrate diligence.
