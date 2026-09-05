# TrustFork 🛡️

[![CI Pipeline](https://github.com/ayush2singh/Trustfork/actions/workflows/ci.yml/badge.svg)](https://github.com/ayush2singh/Trustfork/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**TrustFork** is an asynchronous, partition-tolerant, cryptographically verifiable distributed authorization engine.

It resolves the **Offline Authorization Paradox**: enabling disconnected edge nodes (e.g., regional bank branches, POS terminals, retail kiosks) to safely authorize high-value transactions during network splits while guaranteeing deterministic reconciliation and forward-recovery compensation upon reconnecting.

---

## The Distributed Dilemma

In traditional CP architectures (strict consistency), partitioned nodes must **freeze**:
* ❌ Offline branch cannot disburse loans or process withdrawals.
* ❌ Business grinds to a halt during cloud outages.

In naive AP architectures (high availability), partitioned nodes operate blindly:
* ❌ Edge branches approve loans under outdated policies.
* ❌ Reconnection creates unresolvable double-spending and ledger corruption.

**TrustFork solves this through an AP-with-Verifiable-Convergence model**:
1. Edge nodes evaluate immutable, content-addressed policy graphs.
2. Every offline decision produces an RFC 8785 Ed25519 cryptographic receipt.
3. Logical vector clocks capture causal ordering without relying on NTP clocks.
4. When the network heals, an automated Saga reconciler applies forward-recovery compensation.

👉 **For the full trade-off analysis of all 8 core design choices, see [architecturalDecision.md](architecturalDecision.md).**

---


## Architecture & Workflow

```mermaid
sequenceDiagram
    autonumber
    participant Central as Central Authority (HQ)
    participant Edge as Edge Branch (Branch B)
    participant Customer as Customer / POS
    participant Reconciler as TrustFork Reconciler
    participant Saga as Saga Store (SQLite)

    Note over Central,Edge: 1. Normal Operation (Policy V1: $20,000 Limit)
    Note over Central,Edge: 2. Network Partition Occurs (Branch Disconnected)
    Central->>Central: Policy Update V2 ($10,000 Limit)
    Customer->>Edge: Request Loan ($20,000)
    Edge->>Edge: Evaluates Cached Merkle Policy V1 (ALLOW)
    Edge->>Edge: Signs Ed25519 Receipt (RFC 8785 Canonical)
    Edge->>Customer: Disburses $20,000 Cash
    Note over Central,Edge: 3. Network Heals & Partition Reconnects
    Edge->>Reconciler: Submits Signed Authorization Receipt
    Reconciler->>Reconciler: 1. Verify Ed25519 Signature
    Reconciler->>Reconciler: 2. Check Policy Defensibility in Merkle DAG
    Reconciler->>Reconciler: 3. Causal Vector Clock Check (Divergence Detected!)
    Reconciler->>Saga: Dispatch Forward-Recovery Compensation ($10,000 Excess)
    Saga->>Saga: Idempotent SQLite Execution (COMPENSATION_COMPLETE)
```

---

## Core Technical Pillars

### 1. Distributed Systems: Merkle CRDT & Vector Clocks
* **Merkle Policy DAG (`merkle_crdt.py`)**: Authorization policies are modeled as content-addressed Directed Acyclic Graph (DAG) nodes. Each node hashes its rules, limits, and `parent_hash` with SHA-256. Modifications fork cleanly without silent drift.
* **Vector Clocks (`vector_clock.py`)**: Resolves Lamport logical causality. Categorizes event pairs into `HAPPENS_BEFORE`, `HAPPENS_AFTER`, `EQUAL`, or `CONCURRENT` without depending on unsynchronized hardware clocks.

### 2. Cryptographic Integrity: RFC 8785 Canonical Ed25519
* **Canonical JSON (`receipt.py`)**: Implements RFC 8785 canonical serialization (lexicographically sorted keys, no extraneous whitespace, normalized floats/integers, UTF-8).
* **Ed25519 Digital Signatures**: Every offline decision produces an unforgeable cryptographic receipt. Edge nodes cannot deny or rewrite the policy version they evaluated.

### 3. Fintech Resilience: Sagas & Forward Recovery
* **Forward Recovery (`reconciler.py`)**: When cash or physical goods are handed out offline, database rollbacks are impossible. TrustFork shifts from ACID rollback to **Saga forward-recovery**.
* **Idempotent SQLite Persistence (`saga_store.py`)**: Compensations are keyed deterministically (`compensate_{receipt_id}_{action}`) with atomic SQLite state transitions (`INITIATED` -> `EXECUTING` -> `COMPLETED`).

---

## Evaluator Quickstart

### Prerequisites
* Python 3.12+
* [`uv`](https://docs.astral.sh/uv/) (modern, high-performance Python package manager)

```bash
# Clone the repository
git clone https://github.com/ayush2singh/Trustfork.git
cd Trustfork
```

### Option A: Run Headless Simulation (Terminal)
Executes the complete partition, loan approval under V1, reconnect, reconciliation, and saga clawback:
```bash
python main.py
# Or via uv directly:
uv run python main.py
```

### Option B: Launch Interactive Web Dashboard
Spins up the FastAPI real-time simulation UI with network topology controls:
```bash
uv run --directory app_build python -m uvicorn trustfork.server:app --app-dir src --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser:
* Toggle **Network Partition** on/off.
* Issue loans at Branch B under disconnected state.
* Click **Heal & Reconcile** to observe DAG convergence and Saga execution.

### Option C: Run via Docker (Zero-Install)
Pull and run the prebuilt production container directly from GitHub Container Registry:
```bash
docker run -p 8000:8000 ghcr.io/ayush2singh/trustfork:latest
```

---


## Test Suite & Verification

The test suite covers all edge cases: clock concurrency, signature tampering, indefensible policies, and SQLite persistence.

```bash
uv run --directory app_build pytest
```

All **16 automated tests** pass with 0 warnings.
