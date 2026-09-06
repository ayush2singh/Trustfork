# TrustFork: Distributed Systems & FinTech Edge Cases Catalog

This document provides a comprehensive breakdown of all failure modes, edge cases, Byzantine scenarios, and network partition dilemmas in **TrustFork**, alongside their architectural and algorithmic defenses.

---

## 1. Architectural Defense Pipeline

Every transaction, receipt, and lease passes through these sequential checkpoints:

```
[Incoming Transaction / Receipt from Edge Branch]
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 0: Ingestion & Schema Sanitization (Pydantic / server.py)         │
│ • Catches negative dollar amounts, malformed JSON, and type errors.    │
└───────────────────────┬────────────────────────────────────────────────┘
                        │ Valid Types & Schema
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 1: Cryptographic Integrity & Tamper Check (RFC 8785 + Ed25519)    │
│ • Catches MITM tampering, altered loan amounts, and corrupted keys.    │
└───────────────────────┬────────────────────────────────────────────────┘
                        │ Byte-for-Byte Valid Digital Signature
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 2: Governance & Merkle Ancestry (merkle_crdt.py)                  │
│ • Catches rogue policies, fake rules, and unauthorized governance edits.│
└───────────────────────┬────────────────────────────────────────────────┘
                        │ Proven Ancestry Rooted in Cluster Genesis
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 3: Epoch Validity & Temporal Boundaries (lease.py / reconciler.py)│
│ • Catches expired authorizations and physical clock spoofing.          │
└───────────────────────┬────────────────────────────────────────────────┘
                        │ execution_epoch <= valid_until_epoch
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 4: Scope & Capability Enforcement (lease.py)                      │
│ • Catches privilege escalation (e.g. using a loan lease to buy stock). │
└───────────────────────┬────────────────────────────────────────────────┘
                        │ Action & Resource Match Pre-Approved Lease
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 5: Cumulative Quota & Budget Enforcement (lease.py)               │
│ • Catches branch over-spending beyond pre-authorized mathematical cap. │
└───────────────────────┬────────────────────────────────────────────────┘
                        │ Cumulative Spend <= Usage Limit
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ OUTCOME: Deterministic Finality -> SURVIVES (Zero Clawback)            │
│ (If un-leased or legacy divergence occurs: Durable SQLite Saga Net)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Master Edge Cases Table

| ID | Failure Scenario | Plain English Meaning | How TrustFork Solves It |
| :--- | :--- | :--- | :--- |
| **EC-01** | In-Flight Tampering | A hacker changes $20,000 to $50,000 in transit. | RFC 8785 canonical hash mismatch; Ed25519 throws `InvalidSignature`. |
| **EC-02** | Corrupted Public Keys | A corrupt database row passes bad key bytes. | 32-byte Ed25519 deserialization assert; hard error abort. |
| **EC-03** | JSON Formatting Discrepancies | Python and Go order JSON keys differently, breaking hashes. | RFC 8785 (JCS) sorts keys lexicographically and strips whitespace. |
| **EC-04** | Split-Brain Offline Spend | Branch approves loan under old policy while offline. | Vector clocks detect divergence; 5-point invariant proves safety; Sagas handle deltas. |
| **EC-05** | Double-Click / Replay Attack | User clicks 'Submit' 5 times or network re-sends packet. | SQLite `idempotency_key` primary key constraint ignores duplicates. |
| **EC-06** | Flapping Network Cable | Wi-Fi disconnects and reconnects every 2 seconds. | Atomic batch processing with durable SQLite WAL queue. |
| **EC-07** | Byzantine Rogue Policy | Hacker branch invents a fake policy with a $10M limit. | Merkle DAG recursive traversal to Genesis fails (`ILLEGITIMATE_ANCESTRY`). |
| **EC-08** | Compliant Offline Spend | Branch spent under old limit ($8k), which also complies with new limit ($10k). | Reconciler recognizes zero excess; marks `COMMITTED` without saga. |
| **EC-09** | AI Hallucination in Audits | Cloud LLM invents fake compliance reasons. | 100% Deterministic Semantic NLG in `copilot.py` (Zero AI hallucination). |
| **EC-10** | Lease Parameter Inflation | Dishonest branch edits lease limit from $15k to $50k. | Altered parameter invalidates Central Authority's Ed25519 signature. |
| **EC-11** | Expired Lease / Time Warp | Branch attempts to use a lease after the era has ended. | Logical epoch check: `execution_epoch <= valid_until_epoch`. |
| **EC-12** | Scope Hijacking | Branch uses a 'Home Loan' lease to buy volatile stocks. | Gate 4 checks `action` and `resource` match the lease scope. |
| **EC-13** | Local Quota Overrun | Borrower asks for $16,000 against a $15,000 lease. | Edge branch fails closed locally before dispensing any physical cash. |

---

## 3. Deep-Dive: The 13 Edge Cases Explained

### Category 1: Cryptography & Security

#### EC-01: In-Flight Payload Tampering (The Altered Check)
- **Plain English:** A hacker intercepts the transaction while it is traveling over the network and changes the requested loan amount from $20,000 to $50,000.
- **The Danger:** Central Bank would pay out $50,000 instead of $20,000.
- **How TrustFork Handles It:**
  Before sending, the branch computes a cryptographic SHA-256 fingerprint of the exact data and signs it with its Ed25519 private key. If the hacker alters even a single comma or digit, the fingerprint changes completely. The reconciler notices the signature no longer matches the fingerprint, flags it as `TAMPERED_RECEIPT`, and rejects it immediately.

#### EC-02: Key Deserialization & Corrupted Signatures (The Bad Key)
- **Plain English:** Someone sends random garbage bytes or an incorrectly formatted key instead of a legitimate 32-byte cryptographic public key.
- **The Danger:** Unhandled crashes or memory corruption in the cryptographic library.
- **How TrustFork Handles It:**
  TrustFork verifies that every Ed25519 public key is strictly 32 bytes and lies on the valid elliptic curve. Any malformed key aborts before verification starts.

#### EC-03: JSON Formatting Discrepancies (The Formatting Dispute)
- **Plain English:** In Python, a dictionary might format as `{"amount": 100, "user": "alice"}`. In Go or JavaScript, it might format as `{"user": "alice", "amount": 100}`. They mean the same thing, but their text is different.
- **The Danger:** Standard SHA-256 hashes would be completely different, so valid transactions from other programming languages would be falsely rejected!
- **How TrustFork Handles It:**
  TrustFork implements **RFC 8785 (JSON Canonicalization Scheme)**. Before hashing, keys are sorted alphabetically and all unnecessary spaces are removed.

---

### Category 2: Distributed Systems & Partitions

#### EC-04: Split-Brain Offline Authorization (The Cut Cable)
- **Plain English:** The internet cable between Head Office and Branch B is cut. Head Office lowers loan limits to $10,000. Branch B doesn't know this, so it continues approving $15,000 loans based on its last known rules.
- **The Danger:** Two different realities exist simultaneously. When the cable is plugged back in, Head Office might reject the loans, but Branch B has already handed out physical cash!
- **How TrustFork Handles It:**
  TrustFork uses **Bounded Leases**. Central Bank pre-authorizes Branch B with a capped quota ($15,000) for Epoch 10. Because Branch B stayed inside the pre-authorized lease, Central Bank's 5-point invariant marks it as **`SURVIVES`**. No customer is penalized, and zero rollbacks occur.

#### EC-05: Network Replay Attack & Double-Click (The Impatient User)
- **Plain English:** A user clicks 'Submit' 5 times, or an unreliable router re-sends the same payment packet 5 times after reconnecting.
- **The Danger:** The customer is debited 5 times or issued 5 duplicate clawbacks.
- **How TrustFork Handles It:**
  TrustFork generates an **Idempotency Key** for every transaction (e.g., `compensate_RCPT-101_clawback`). This key is stored as a `PRIMARY KEY UNIQUE` constraint in SQLite. When duplicate packets arrive, SQLite rejects the duplicate insert and returns the already-completed record without re-executing.

#### EC-06: Rapid Network Partition Flapping (The Loose Cable)
- **Plain English:** The network connection flickers rapidly—connected for 1 second, disconnected for 2 seconds, connected for 1 second.
- **The Danger:** Transactions get stuck in half-finished states if the connection drops midway.
- **How TrustFork Handles It:**
  Receipts are stored durably on local disk at the edge branch. When connectivity flickers, reconciliation processes receipts in **atomic, non-blocking batches**. If a batch is interrupted, the transaction remains queued on disk until connectivity stabilizes.

---

### Category 3: Governance & Merkle Policy Ancestry

#### EC-07: Byzantine Rogue Policy Hash (The Counterfeit Rulebook)
- **Plain English:** A rogue employee or malware at Branch B creates their own fake rule: *"Ayush can withdraw $10,000,000"* with a fake hash `deadbeef...` and approves it offline.
- **The Danger:** The rogue branch claims the withdrawal was valid under its local rulebook.
- **How TrustFork Handles It:**
  At Gate 2, the reconciler checks the **Merkle DAG**. It walks backwards through the cryptographic parent hashes. Because `deadbeef...` does not connect to the Central Bank's Genesis block, the reconciler flags it as `ILLEGITIMATE_POLICY_ANCESTRY` and rejects it.

#### EC-08: In-Policy Compliant Offline Approval (The Harmless Disbursal)
- **Plain English:** While offline, Branch B approves a loan for $8,000. Meanwhile, Central Bank reduced the maximum limit from $20,000 to $10,000.
- **The Danger:** A naive system might see different policy version numbers and trigger an unnecessary, panic-inducing clawback.
- **How TrustFork Handles It:**
  The reconciler checks the numbers: $8,000 is under the old limit ($20,000) AND under the new limit ($10,000). The reconciler commits the transaction directly as `COMMITTED` (`is_divergent = False`) and triggers zero sagas.

---

### Category 4: AI Copilot & Observability

#### EC-09: Cloud LLM Outages & Hallucination (The Unreliable AI)
- **Plain English:** Using ChatGPT or Gemini to explain banking errors. What happens if the AI makes up a fake law, hallucinates a transaction, or the internet to OpenAI goes down?
- **The Danger:** Bank submits false audit reports to regulators, or audit tools freeze during an internet outage.
- **How TrustFork Handles It:**
  TrustFork’s Audit Copilot (`copilot.py`) uses **100% Deterministic Rule-Based Natural Language Generation**. It maps mathematical graph relations directly to certified English sentences. It runs in `<1 millisecond`, works completely offline, requires zero API keys, and has zero hallucination risk.

---

### Category 5: Bounded Leases & The 5-Point Invariant

#### EC-10: Lease Parameter Inflation (The Forged Allowance)
- **Plain English:** A corrupt branch manager takes a signed lease for $15,000 and edits the file on disk to say $50,000.
- **The Danger:** The branch attempts to disburse $50,000 of the bank's funds.
- **How TrustFork Handles It:**
  The lease limit is part of the payload signed by Central's Ed25519 private key. Modifying `$15,000` to `$50,000` changes the canonical byte hash. At Gate 1, signature verification fails with `REJECTED_SIGNATURE`.

#### EC-11: Expired Lease / Time Warp (The Stale Voucher)
- **Plain English:** A branch tries to authorize a loan using a lease from last month whose validity has expired.
- **The Danger:** Authorizing transactions under outdated risk allowances.
- **How TrustFork Handles It:**
  Gate 3 checks the discrete **Logical Epoch**: `execution_epoch <= valid_until_epoch`. If the lease was only valid until Epoch 5, and the cluster is on Epoch 6, the transaction is rejected as `EXPIRED_LEASE`. Because epochs are integer counters, local PC clock tampering cannot bypass this.

#### EC-12: Scope Hijacking / Privilege Escalation (The Misused Budget)
- **Plain English:** A branch has a lease authorized for `LOAN_DISBURSEMENT` on `RETAIL_ACCOUNTS`, but attempts to use it to authorize a multi-million-dollar `DERIVATIVES_TRADE`.
- **The Danger:** Unauthorized high-risk operations disguised under low-risk leases.
- **How TrustFork Handles It:**
  Gate 4 verifies capability matching: the transaction's requested `action` and `resource` must match the lease's pre-approved scope. Mismatches are rejected with `SCOPE_MISMATCH`.

#### EC-13: Local Quota Overrun (The Empty Card)
- **Plain English:** A branch has a $15,000 lease. It has already disbursed $12,000. A customer walks in asking for $5,000.
- **The Danger:** Disbursing $5,000 would exceed the $15,000 cap by $2,000.
- **How TrustFork Handles It:**
  The branch's local edge engine checks `remaining_limit()` ($3,000). Because $5,000 > $3,000, the edge **fails closed locally**. The transaction is declined on the spot. No physical cash leaves the vault.

---

## 4. Architectural Philosophy of Edge Case Handling

1. **At the Edge (Proactive Prevention):**
   We fail-closed locally within pre-authorized cryptographic bounded leases so unauthorized funds are never disbursed.

2. **At Reconciliation (The 5-Point Verification Invariant):**
   We enforce a deterministic **5-Point Verification Invariant** in `reconciler.py` that guarantees all compliant edge transactions achieve permanent finality (**`SURVIVES`**) with zero clawbacks:
   - **Point 1 (Cryptographic Authenticity):** The lease's Ed25519 digital signature is mathematically valid over the RFC 8785 canonical JSON payload.
   - **Point 2 (Governance Lineage):** The lease's `policy_hash` is a provable ancestor of the active cluster governance root in the Merkle DAG.
   - **Point 3 (Temporal Era Boundary):** The transaction execution epoch satisfies `execution_epoch <= valid_until_epoch` (immune to NTP wall-clock drift).
   - **Point 4 (Scope & Capability Match):** The requested `(action, resource)` matches the lease's pre-approved authorization scope (Principle of Least Privilege).
   - **Point 5 (Cumulative Quota Enforcement):** The transaction amount satisfies `cumulative_spend + amount <= usage_limit`.

   *Guaranteed Outcome:* If all 5 conditions hold, the verdict is **`SURVIVES`** with zero clawbacks, zero rollbacks, and zero saga side-effects (`compensation = None`).

3. **At the Safety Net (Reactive Forward Recovery):**
   For any un-leased legacy divergence or edge over-allocations, our durable SQLite Saga Orchestrator executes idempotent forward recovery so that the system never crashes, never duplicates charges, and maintains an airtight audit trail.
