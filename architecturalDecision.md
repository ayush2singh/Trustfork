# Architectural Decision Records (ADRs) 🏛️

This document records the foundational architectural decisions made in **TrustFork**, detailing the context, decision, alternatives considered, and explicit trade-offs.

---

## ADR 001: Choose AP with Verifiable Convergence over Strict CP (CAP Theorem)

* **Status**: Accepted
* **Context**: Regional bank branches and POS retail kiosks frequently suffer network partitions due to ISP cuts or cloud outages. In traditional CP systems (strict consistency), partitioned nodes must freeze, blocking loan disbursements and ATM withdrawals.
* **Decision**: Adopt an **AP model (Availability + Partition Tolerance)** with eventual, verifiable convergence. Allow edge nodes to authorize requests offline and sign verifiable receipts.
* **Alternatives Considered**:
  * *Strict CP (Two-Phase Commit)*: Halts offline branch operation. Unacceptable for physical business continuity.
  * *Uncoordinated AP*: Approves transactions without cryptographic proofs or causal tracking, causing irrecoverable double-spending and ledger fraud.
* **Trade-offs**:
  * ✅ **Advantage**: 100% edge availability; retail business never freezes.
  * ⚠️ **Trade-off**: The bank accepts temporary financial exposure during the partition window until reconciliation executes.

---

## ADR 002: Content-Addressed Merkle Policy DAG over Incrementing Version Counters

* **Status**: Accepted
* **Context**: Policies (e.g., maximum loan limits) change concurrently at headquarters and regional branches during network splits. Simple incrementing version counters (`v1`, `v2`, `v3`) cannot represent branching or detect concurrent divergent edits.
* **Decision**: Model authorization policies as immutable, content-addressed Directed Acyclic Graph (DAG) nodes (`PolicyNode` in `merkle_crdt.py`), where each node's SHA-256 hash commits to its rules and its `parent_hash`.
* **Alternatives Considered**:
  * *Monotonic Integers / SemVer strings*: Overwritten easily; silent configuration drift occurs when two nodes publish conflicting "v2" policies.
  * *Distributed Lock Manager (DLM / Raft)*: Requires quorum; impossible during network partitions.
* **Trade-offs**:
  * ✅ **Advantage**: Tamper-proof policy immutability; automatic fork detection; complete audit trail.
  * ⚠️ **Trade-off**: Slightly higher storage and hashing overhead compared to a single integer row in a SQL table.

---

## ADR 003: RFC 8785 Canonical JSON + Ed25519 Signatures over Standard JSON / RSA

* **Status**: Accepted
* **Context**: Offline receipts must provide non-repudiation: branches cannot deny the policy they evaluated. Standard JSON serialization varies by whitespace and key order across platforms, causing signature verification to break.
* **Decision**: Enforce RFC 8785 JSON Canonicalization Rules (lexicographically sorted keys, no whitespace, exact numeric formatting) and sign payloads with Ed25519 (`ReceiptSigner` in `receipt.py`).
* **Alternatives Considered**:
  * *Standard `json.dumps()`*: Non-deterministic across Python versions and other languages; subtle key re-orderings invalidate signatures.
  * *RSA-2048 / RSA-4096*: Massive signature sizes (256-512 bytes) and slow signing/verification speeds on edge hardware.
* **Trade-offs**:
  * ✅ **Advantage**: Fast signing/verification (<1ms), compact 64-byte signatures, byte-level interoperability across languages.
  * ⚠️ **Trade-off**: Requires strict canonical serialization overhead before signing or hashing.

---

## ADR 004: Lamport Vector Clocks over Physical Wall-Clock Timestamps (NTP)

* **Status**: Accepted
* **Context**: When reconciling offline events, determining whether an edge approval occurred before, after, or concurrently with a central policy change is vital.
* **Decision**: Use Vector Clocks (`vector_clock.py`) to model logical causality, categorizing event pairs into `HAPPENS_BEFORE`, `HAPPENS_AFTER`, `EQUAL`, or `CONCURRENT`.
* **Alternatives Considered**:
  * *System Timestamps (`time.time()`)*: Highly vulnerable to NTP drift, clock skew, manual clock tampering, and leap seconds.
  * *TrueTime (Google Spanner / GPS atomic clocks)*: Requires proprietary, specialized hardware unavailable on ordinary edge nodes.
* **Trade-offs**:
  * ✅ **Advantage**: 100% mathematically deterministic causal ordering; completely immune to clock skew or NTP desynchronization.
  * ⚠️ **Trade-off**: Vector clock size grows linearly with the number of participating nodes ($O(N)$).

---

## ADR 005: Saga Forward-Recovery with SQLite Idempotency over ACID Database Rollbacks

* **Status**: Accepted
* **Context**: In physical business systems (banking, retail, logistics), real-world actions cannot be undone via database `ROLLBACK`. When Branch B hands out physical cash to a customer offline under a policy that diverged from central authority, the money has physically left the premises.
* **Decision**: Implement the **Saga Pattern** (`saga_orchestrator.py`, `saga_store.py`) to execute forward-recovery compensating actions (e.g. `clawback`, `hold`, `overdraft_charge`) persisted idempotently in SQLite.
* **Alternatives Considered**:
  * *Two-Phase Commit (2PC)*: Blocks indefinitely during network partitions; fails availability.
  * *Pessimistic Locking*: Requires live cluster connectivity; impossible when disconnected.
* **Trade-offs**:
  * ✅ **Advantage**: Matches physical reality; idempotent execution prevents double-compensation; non-blocking recovery.
  * ⚠️ **Trade-off**: Requires explicit compensation logic for every business action; eventual consistency window exists until compensation completes.

---

## ADR 006: Semantic Version Tag-Gated CD Delivery (`v*`) over Branch-Push Triggers


* **Status**: Accepted
* **Context**: Continuous Deployment must package and publish production container images to GitHub Container Registry (`ghcr.io`) without polluting registries with unstable development commits.
* **Decision**: Restrict the CD pipeline (`cd.yml`) to trigger strictly on Git version tags (`v*`), while CI (`ci.yml`) runs on all commits and PRs to `main`.
* **Alternatives Considered**:
  * *Auto-deploy on every push to `main`*: Leads to image churn, potential deployment of incomplete features, and tag pollution in container registries.
  * *Manual UI Dispatch*: Lacks automated Git commit-to-release traceability.
* **Trade-offs**:
  * ✅ **Advantage**: Strict SemVer compliance; production releases are deliberate and immutable; clear audit trail.
  * ⚠️ **Trade-off**: Requires developers to create and push a Git tag (`git tag vX.Y.Z`) to trigger deployment.
