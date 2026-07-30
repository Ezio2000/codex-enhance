# Security Finder Handbook

Use this handbook only for the Security specialty. Inspect every assigned
review unit against `SE-01` through `SE-09` exactly once and apply every
surface supplement exposed by the neutral context inventory. A security smell
or missing best practice is a search cue, not a candidate.

## Contents

1. Security proof and boundary rules
2. `SE-01` Attack surface and trust boundaries
3. `SE-02` Authentication and session identity
4. `SE-03` Authorization, ownership, and tenancy
5. `SE-04` Injection and unsafe interpretation
6. `SE-05` Files, URLs, processes, and deserialization
7. `SE-06` Secrets, privacy, and sensitive-data lifecycle
8. `SE-07` Cryptography, tokens, and integrity
9. `SE-08` Supply chain, configuration, and deployment
10. `SE-09` Disclosure and denial of service
11. Surface supplements `SE-S01` through `SE-S07`
12. Coverage ledger

## Security proof and boundary rules

Return a candidate only when the evidence closes:

```text
attacker_capability
attacker_controlled_source
identity_and_trust_crossings
existing_controls_and_bypass
sensitive_interpreter_operation_sink_or_asset
deployment_and_configuration_preconditions
CIA_impact: confidentiality | integrity | availability
practical_attack_scenario
```

Read the complete source-to-sink or asset path, including normalization,
authorization at the final operation, encoding/parameterization, deployment
isolation, privileges, logging, and tests. Look for a dominating control and
record disconfirming evidence. Reject when the attacker cannot reach or
control the source, an effective guard dominates the sink, the protected asset
is absent, the deployment premise is contradicted, or the impact is only
hypothetical.

Exclude:

- ordinary correctness and compatibility defects without CIA impact;
- non-adversarial performance and capacity concerns (`standardize`);
- readability, naming, or visual polish (`beautify`);
- concept deletion and local complexity (`simplify`);
- architecture or design-boundary cost without an attack path (`design`);
- generic hardening, defense-in-depth, missing headers, or dependency names
  without demonstrated reachability and impact.

Never expose secret values or personal data in evidence. Use a redacted
fingerprint, location, data class, and flow instead.

## SE-01 Attack surface and trust boundaries

**Trigger:** The review unit accepts data, identity, events, files, network
responses, configuration, plugins, or commands from a less-trusted principal,
or performs a privileged operation across a boundary.

**Inspect:** Inventory entry point, attacker/principal, trust zones, protected
assets, transformations, validation, identity binding, privileges, sinks, and
deployment assumptions. Trace complete paths rather than isolated calls.

**Candidate gate:** Identify a concrete crossing with missing or bypassable
control and close the CIA-impact chain. An exposed endpoint or boundary alone
is not a flaw.

## SE-02 Authentication and session identity

**Trigger:** Code establishes, restores, refreshes, delegates, or invalidates
identity through credentials, sessions, cookies, tokens, device state, SSO,
API keys, or recovery flows.

**Inspect:** Trace issuance, binding, transport, storage, expiry, rotation,
revocation, replay resistance, fixation, step-up requirements, recovery, and
failure behavior. Verify signature/issuer/audience/time checks and trust in
forwarded identity.

**Candidate gate:** Show how an attacker forges, steals, replays, fixes,
confuses, or retains an identity and reaches a protected action or data asset.
Configuration-independent advice is not enough.

## SE-03 Authorization, ownership, and tenancy

**Trigger:** An authenticated or anonymous principal selects an object,
tenant, account, operation, role, scope, or administrative action.

**Inspect:** Check authorization at the final data or side-effect boundary,
object ownership, tenant predicates, role/scope composition, defaults, batch
operations, indirect references, cache keys, and confused-deputy paths.

**Candidate gate:** Demonstrate a reachable principal/object/action tuple that
the policy forbids but the code permits. Authentication without an
authorization bypass is not a candidate.

## SE-04 Injection and unsafe interpretation

**Trigger:** Untrusted data enters SQL/NoSQL queries, shells, templates, HTML,
JavaScript, expressions, regular expressions, headers, logs, code generation,
interpreters, or structured query/filter languages.

**Inspect:** Follow data through decoding and normalization to the exact
interpreter context. Check parameterization, context-specific encoding,
allowlists, command construction, secondary interpretation, and whether a
safe wrapper dominates every route.

**Candidate gate:** Supply a practical payload shape or manipulation that
crosses the missing/bypassable control and changes execution, data access, or
protected output. String concatenation by itself is not proof.

## SE-05 Files, URLs, processes, and deserialization

**Trigger:** Untrusted input influences a path, archive member, URL/host,
redirect, process executable/argument/environment, dynamic module, parser, or
deserializer.

**Inspect:** Check canonicalization order, root containment, symlink/race
behavior, scheme/host/IP validation, redirects and DNS rebinding, argument
boundaries, environment inheritance, parser limits, type allowlists, archive
extraction, and privilege context.

**Candidate gate:** Trace controllable input to unintended file/network/process
access or object construction and state the CIA impact. A sensitive API name
without control of its security-relevant operand is not a finding.

## SE-06 Secrets, privacy, and sensitive-data lifecycle

**Trigger:** Credentials, tokens, keys, personal data, regulated data, or
private content is collected, stored, logged, cached, exported, retained, or
deleted.

**Inspect:** Classify the data and trace collection, access, encryption,
redaction, logs/errors/telemetry, backups, caches, transport, retention,
deletion, tenant boundaries, and least privilege. Never print the value.

**Candidate gate:** Show a reachable unauthorized disclosure, use, retention,
or deletion failure affecting sensitive data. Mere presence of sensitive data
or lack of ideal minimization is insufficient without a concrete exposure.

## SE-07 Cryptography, tokens, and integrity

**Trigger:** Code generates randomness, hashes passwords, encrypts, signs,
verifies, compares authenticators, derives keys, creates reset/invite tokens,
or validates integrity/freshness.

**Inspect:** Confirm algorithm/mode, library contract, key source and
lifecycle, nonce/IV uniqueness, entropy, parameter strength, signature
coverage, canonicalization, constant-time needs, downgrade/fallback behavior,
expiry, replay, and failure handling.

**Candidate gate:** Demonstrate how the actual construction permits forgery,
decryption, guessing, replay, downgrade, or integrity bypass under realistic
attacker capability. Algorithm-name preference alone is not proof.

## SE-08 Supply chain, configuration, and deployment

**Trigger:** Dependencies, plugins, build scripts, CI workflows, artifacts,
containers, update channels, environment configuration, permissions, or
deployment defaults affect what code runs or what it can access.

**Inspect:** Establish pinned versions and provenance, install/build hooks,
artifact verification, CI event and token permissions, untrusted contribution
paths, base images, runtime users, exposed services, debug modes, secret
boundaries, and production defaults. Use lock files only as version/provenance
evidence.

**Candidate gate:** Trace a realistic contributor, dependency, artifact, or
configuration manipulation to execution, privilege, data, or exposure with
CIA impact. A stale package or broad permission alone is not a finding unless
the exploit path and affected asset are established.

## SE-09 Disclosure and denial of service

**Trigger:** Errors, timing, logs, metadata, responses, diagnostics, or
resource behavior may expose protected information or let an untrusted party
consume disproportionate CPU, memory, I/O, threads, descriptors, queues, or
external spend.

**Inspect:** Trace attacker-controlled frequency and scale, rate and size
limits, timeouts, quotas, amplification, algorithmic growth, retries, fan-out,
backpressure, isolation, redaction, cache behavior, and observable response
differences.

**Candidate gate:** For disclosure, show what protected fact is learnable and
by whom. For denial of service, give an attacker-triggered cost model and
reachable exhaustion or material service degradation. Route ordinary
non-adversarial slowness to `standardize`.

## Surface supplements

Apply each supplement when the neutral `surface_inventory` exposes it. A
supplement adds focused inspection; it does not replace `SE-01` through
`SE-09`.

### SE-S01 HTTP, RPC, and API

Inspect route/method exposure, authentication placement, object/tenant
authorization, CSRF where ambient authority applies, CORS impact, request
smuggling assumptions, headers/cookies, upload and body limits, redirects,
response caching, and error disclosure.

### SE-S02 Persistence and migrations

Inspect tenant/ownership predicates, query construction, row-level controls,
transactions and integrity constraints, migration privileges, backups,
retention/deletion, encryption boundaries, and data returned through caches or
search indexes.

### SE-S03 Queues, events, and jobs

Inspect producer identity, message authenticity, tenant binding, replay,
deduplication, ordering assumptions, poison-message handling, retry
amplification, payload validation, worker privileges, and dead-letter data.

### SE-S04 Filesystem, URL, process, and deserialization

Inspect canonical containment, symlinks and races, archive members, scheme and
address allowlists, redirects/DNS changes, argument and environment
boundaries, executable selection, parser limits, and type allowlists.

### SE-S05 UI, client, and native surfaces

Inspect DOM and rich-text sinks, deep links, webviews, IPC origin and sender
identity, local secret/token storage, clipboard/screenshots, update channels,
certificate trust, exported components, and client-side authorization
assumptions.

### SE-S06 CLI, configuration, infrastructure, and CI

Inspect untrusted flags/config/environment, path and shell handling, secret
redaction, file permissions, workflow trigger context, token permissions,
artifact boundaries, pull-request code execution, production defaults, debug
exposure, network policy, and runtime identity.

### SE-S07 Dependencies, builds, and supply chain

Inspect source and registry provenance, version constraints and lock evidence,
install/build hooks, generated artifacts, checksums/signatures, update
channels, base images, transitive execution, maintainer boundaries, and
dependency use on attacker-reachable paths.

## Coverage ledger

Return exactly one inspection record for each `(review_unit, SE-01..SE-09)`
pair and for each applicable `(review_unit, SE-S01..SE-S07)` pair:

```text
role: Security
review_kind: security
check_id: SE-01..SE-09 | SE-S01..SE-S07
status: checked_clear | candidate | not_applicable | blocked
```

For supplements that the surface inventory explicitly evaluates as absent,
record the shared orchestration contract's evidenced `not_applicable`
disposition at the appropriate inventory level; do not silently omit them.
Populate every evidence field required by the shared finding contract.
`checked_clear` identifies the performed action and disconfirming evidence.
Missing, duplicate, unknown, or `blocked` rows make the unit uncovered. Link
every candidate to its originating inspection records and set
`review_kind: security`; never assign priority or confidence.
