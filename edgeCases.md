# TrustFork: Distributed Systems & FinTech Edge Cases Catalog
## (Plain-English Defense Guide for Evaluator Presentations)

This document explains every failure mode, edge case, and attack scenario in **TrustFork**. It translates complex distributed systems terminology into plain, intuitive English with real-world analogies so that **no evaluator can catch you off guard with jargon**.

---

## 1. Plain-English Glossary of Evaluator Buzzwords

If an evaluator interrupts and asks: *"What does that word actually mean?"*, use these exact definitions:

| Technical Buzzword | What It Actually Means in Plain English | Real-World Analogy |
| :--- | :--- | :--- |
| **Byzantine Node** | A computer that is hacked, buggy, or lying about its state. | A corrupt bank teller who makes up fake transactions. |
| **Split-Brain** | Two isolated servers that lose contact and both make conflicting decisions independently. | Two pilots in separate cockpits both pulling the flight stick in opposite directions because their intercom broke. |
| **Idempotency** | Performing an action multiple times produces the exact same result as performing it once. | Pressing an elevator button 10 times—the elevator still arrives only once, and you are charged only once. |
| **MITM (Man-In-The-Middle)** | An attacker sitting between two servers who intercepts and tampers with messages in transit. | An untrusted mailman opening an envelope, changing the check amount from $20 to $500, and resealing it. |
| **Canonicalization (RFC 8785)** | Enforcing one single, universal text format (spacing, key order) so computers don't disagree over trivial formatting. | Insisting everyone writes dates as `YYYY-MM-DD` so `04/05/26` isn't confused between April 5th and May 4th. |
| **Zombie Saga** | A background compensation task that got frozen halfway because the computer suddenly lost power. | A cashier counting out cash for a refund, but the power goes out before handing it over; on restart, the cashier resumes where they left off. |
| **Partition Flapping** | A network connection that rapidly connects, disconnects, and reconnects every few milliseconds. | A loose HDMI cable flickering between static and picture. |
| **Non-Repudiation** | Proof of identity so airtight that the sender cannot claim *"I never sent that"*. | A notarized signature on a legal contract witnessed by five bankers. |
| **Fail-Closed** | If a safety check is uncertain or fails, default to rejecting the transaction to prevent loss. | An ATM locking its cash vault shut when an error occurs, instead of accidentally spitting out dollar bills. |
| **Logical Epoch** | A monotonically increasing integer counter representing a governance era, completely immune to clock drift. | Numbered chapters in a book. Chapter 3 always comes before Chapter 4, regardless of what your wristwatch says. |

---

## 2. Complete Architectural Defense Pipeline

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

## 3. Master Edge Cases Table (Plain English & Technical Defense)

| ID | Failure Scenario | Plain English Meaning | How TrustFork Solves It | Evaluator Defense Pitch |
| :--- | :--- | :--- | :--- | :--- |
| **EC-01** | In-Flight Tampering | A hacker changes $20,000 to $50,000 in transit. | RFC 8785 canonical hash mismatch; Ed25519 throws `InvalidSignature`. | *"Any altered character breaks the digital signature at Gate 1 before any money moves."* |
| **EC-02** | Corrupted Public Keys | A corrupt database row passes bad key bytes. | 32-byte Ed25519 deserialization assert; hard error abort. | *"Invalid curve points or corrupted keys are rejected at deserialization."* |
| **EC-03** | JSON Formatting Discrepancies | Python and Go order JSON keys differently, breaking hashes. | RFC 8785 (JCS) sorts keys lexicographically and strips whitespace. | *"RFC 8785 ensures identical byte representations across all programming languages."* |
| **EC-04** | Split-Brain Offline Spend | Branch approves loan under old policy while offline. | Vector clocks detect divergence; 5-point invariant proves safety; Sagas handle deltas. | *"If within bounded lease, it SURVIVES; if un-leased, the saga adjusts the delta without crash."* |
| **EC-05** | Double-Click / Replay Attack | User clicks 'Submit' 5 times or network re-sends packet. | SQLite `idempotency_key` primary key constraint ignores duplicates. | *"Our idempotency key guarantees that repeating a transaction 10 times executes it only once."* |
| **EC-06** | Flapping Network Cable | Wi-Fi disconnects and reconnects every 2 seconds. | Atomic batch processing with durable SQLite WAL queue. | *"Transactions queue safely on disk; reconciler processes atomic batches without half-states."* |
| **EC-07** | Byzantine Rogue Policy | Hacker branch invents a fake policy with a $10M limit. | Merkle DAG recursive traversal to Genesis fails (`ILLEGITIMATE_ANCESTRY`). | *"The policy hash must trace back cryptographically to the cluster's genesis root."* |
| **EC-08** | Compliant Offline Spend | Branch spent under old limit ($8k), which also complies with new limit ($10k). | Reconciler recognizes zero excess; marks `COMMITTED` without saga. | *"No divergence exists if the spend is legal under both old and new governance rules."* |
| **EC-09** | Mid-Flight Power Cut | Server crashes while compensating an overdrawn account. | SQLite WAL mode + `get_pending()` recovery daemon on restart. | *"Write-Ahead Logging ensures zero lost tasks; pending sagas automatically resume on reboot."* |
| **EC-10** | Accounting Sign Confusion | Auditor doesn't know if $10,000 is a debit or a credit. | Explicit net debit convention (`-$10,000`) with `CLAWBACK` badge. | *"Every compensating entry is formalized as a signed net balance reduction."* |
| **EC-11** | AI Hallucination in Audits | Cloud LLM invents fake compliance reasons. | 100% Deterministic Semantic NLG in `copilot.py` (Zero AI hallucination). | *"Our audit copilot uses mathematical finite-state logic, not probabilistic LLMs."* |
| **EC-12** | Negative / Malformed Money | User submits a loan for `-$5,000` or `"free_money"`. | Pydantic model validation aborts with HTTP 422 immediately. | *"Strict input schema validation eliminates malformed payloads at the perimeter."* |
| **EC-13** | Lease Parameter Inflation | Dishonest branch edits lease limit from $15k to $50k. | Altered parameter invalidates Central Authority's Ed25519 signature. | *"The branch cannot forge Central's private key; tampered limits fail Gate 1 immediately."* |
| **EC-14** | Expired Lease / Time Warp | Branch attempts to use a lease after the era has ended. | Logical epoch check: `execution_epoch <= valid_until_epoch`. | *"Logical epochs prevent stale lease re-use and are completely immune to clock drift."* |
| **EC-15** | Scope Hijacking | Branch uses a 'Home Loan' lease to buy volatile stocks. | Gate 4 checks `action` and `resource` match the lease scope. | *"Leases are purpose-bound; a mortgage lease cannot authorize a trading disbursal."* |
| **EC-16** | Local Quota Overrun | Borrower asks for $16,000 against a $15,000 lease. | Edge branch fails closed locally before dispensing any physical cash. | *"The edge node enforces the remaining quota locally; the vault never opens for over-limit amounts."* |

---

## 4. Deep-Dive: The 16 Edge Cases Explained in Plain Words

### Category 1: Cryptography & Security

#### EC-01: In-Flight Payload Tampering (The Altered Check)
- **Plain English:** A hacker intercepts the transaction while it is traveling over the network and changes the requested loan amount from $20,000 to $50,000.
- **The Danger:** Central Bank would pay out $50,000 instead of $20,000.
- **How TrustFork Handles It:**
  Before sending, the branch computes a cryptographic SHA-256 fingerprint of the exact data and signs it with its Ed25519 private key. If the hacker alters even a single comma or digit, the fingerprint changes completely. The reconciler notices the signature no longer matches the fingerprint, flags it as `TAMPERED_RECEIPT`, and rejects it immediately.
- **What to Say to Evaluator:**
  > *"Because digital signatures are tied to the exact byte-level SHA-256 digest of the payload, any tampering in transit causes an instant InvalidSignature exception at Gate 1."*

#### EC-02: Key Deserialization & Corrupted Signatures (The Bad Key)
- **Plain English:** Someone sends random garbage bytes or an incorrectly formatted key instead of a legitimate 32-byte cryptographic public key.
- **The Danger:** Unhandled crashes or memory corruption in the cryptographic library.
- **How TrustFork Handles It:**
  TrustFork verifies that every Ed25519 public key is strictly 32 bytes and lies on the valid elliptic curve. Any malformed key aborts before verification starts.
- **What to Say to Evaluator:**
  > *"We enforce strict 32-byte public key validation using cryptography.io primitives, terminating any malformed input at deserialization."*

#### EC-03: JSON Formatting Discrepancies (The Formatting Dispute)
- **Plain English:** In Python, a dictionary might format as `{"amount": 100, "user": "alice"}`. In Go or JavaScript, it might format as `{"user": "alice", "amount": 100}`. They mean the same thing, but their text is different.
- **The Danger:** Standard SHA-256 hashes would be completely different, so valid transactions from other programming languages would be falsely rejected!
- **How TrustFork Handles It:**
  TrustFork implements **RFC 8785 (JSON Canonicalization Scheme)**. Before hashing, keys are sorted alphabetically and all unnecessary spaces are removed.
- **What to Say to Evaluator:**
  > *"We implement RFC 8785 canonicalization to ensure identical byte-level serialization across all programming runtimes, preventing false signature rejections."*

---

### Category 2: Distributed Systems & Partitions

#### EC-04: Split-Brain Offline Authorization (The Cut Cable)
- **Plain English:** The internet cable between Head Office and Branch B is cut. Head Office lowers loan limits to $10,000. Branch B doesn't know this, so it continues approving $15,000 loans based on its last known rules.
- **The Danger:** Two different realities exist simultaneously. When the cable is plugged back in, Head Office might reject the loans, but Branch B has already handed out physical cash!
- **How TrustFork Handles It:**
  TrustFork uses **Bounded Leases**. Central Bank pre-authorizes Branch B with a capped quota ($15,000) for Epoch 10. Because Branch B stayed inside the pre-authorized lease, Central Bank's 5-point invariant marks it as **`SURVIVES`**. No customer is penalized, and zero rollbacks occur.
- **What to Say to Evaluator:**
  > *"Under CAP, we prioritize availability via pre-authorized bounded leases. Because the edge stayed within its pre-allocated quota, reconciliation guarantees permanent finality (`SURVIVES`) with zero clawbacks."*

#### EC-05: Network Replay Attack & Double-Click (The Impatient User)
- **Plain English:** A user clicks 'Submit' 5 times, or an unreliable router re-sends the same payment packet 5 times after reconnecting.
- **The Danger:** The customer is debited 5 times or issued 5 duplicate clawbacks.
- **How TrustFork Handles It:**
  TrustFork generates an **Idempotency Key** for every transaction (e.g., `compensate_RCPT-101_clawback`). This key is stored as a `PRIMARY KEY UNIQUE` constraint in SQLite. When duplicate packets arrive, SQLite rejects the duplicate insert and returns the already-completed record without re-executing.
- **What to Say to Evaluator:**
  > *"Our Saga store enforces unique primary key idempotency constraints, guaranteeing that network retransmissions are completely harmless."*

#### EC-06: Rapid Network Partition Flapping (The Loose Cable)
- **Plain English:** The network connection flickers rapidly—connected for 1 second, disconnected for 2 seconds, connected for 1 second.
- **The Danger:** Transactions get stuck in half-finished states if the connection drops midway.
- **How TrustFork Handles It:**
  Receipts are stored durably on local disk at the edge branch. When connectivity flickers, reconciliation processes receipts in **atomic, non-blocking batches**. If a batch is interrupted, the transaction remains queued on disk until connectivity stabilizes.
- **What to Say to Evaluator:**
  > *"Batch reconciliation operates atomically over durable SQLite queues; link oscillation never corrupts state or drops receipts."*

---

### Category 3: Governance & Merkle Policy Ancestry

#### EC-07: Byzantine Rogue Policy Hash (The Counterfeit Rulebook)
- **Plain English:** A rogue employee or malware at Branch B creates their own fake rule: *"Ayush can withdraw $10,000,000"* with a fake hash `deadbeef...` and approves it offline.
- **The Danger:** The rogue branch claims the withdrawal was valid under its local rulebook.
- **How TrustFork Handles It:**
  At Gate 2, the reconciler checks the **Merkle DAG**. It walks backwards through the cryptographic parent hashes. Because `deadbeef...` does not connect to the Central Bank's Genesis block, the reconciler flags it as `ILLEGITIMATE_POLICY_ANCESTRY` and rejects it.
- **What to Say to Evaluator:**
  > *"A policy is only valid if its cryptographic parent chain traverses directly back to the cluster Genesis root in the Merkle DAG."*

#### EC-08: In-Policy Compliant Offline Approval (The Harmless Disbursal)
- **Plain English:** While offline, Branch B approves a loan for $8,000. Meanwhile, Central Bank reduced the maximum limit from $20,000 to $10,000.
- **The Danger:** A naive system might see different policy version numbers and trigger an unnecessary, panic-inducing clawback.
- **How TrustFork Handles It:**
  The reconciler checks the numbers: $8,000 is under the old limit ($20,000) AND under the new limit ($10,000). The reconciler commits the transaction directly as `COMMITTED` (`is_divergent = False`) and triggers zero sagas.
- **What to Say to Evaluator:**
  > *"If the transaction complies with both offline and online policy boundaries, the reconciler commits it directly with zero compensation overhead."*

---

### Category 4: Durability & Sagas

#### EC-09: Mid-Flight Server Crash (The Zombie Saga)
- **Plain English:** Central Bank starts processing a compensation saga, but right in the middle, someone accidentally unplugs the server's power cable.
- **The Danger:** In-memory systems lose all track of the transaction, leaving money missing without an audit trail.
- **How TrustFork Handles It:**
  All saga state changes are written to SQLite in **Write-Ahead Logging (WAL)** mode. On server reboot, a background recovery worker runs `saga_store.get_pending()`, detects any unfinished `COMPENSATION_INITIATED` tasks, and finishes them.
- **What to Say to Evaluator:**
  > *"Durable SQLite WAL logging combined with our `get_pending()` recovery daemon ensures zero zombie sagas survive a server crash."*

#### EC-10: Accounting Balance Ambiguity (The Confusing Sign)
- **Plain English:** An audit report displays `Compensation: $10,000`. Does this mean the bank gave the customer $10,000, or took $10,000 back?
- **The Danger:** Financial auditors cannot determine if the ledger balanced correctly.
- **How TrustFork Handles It:**
  All clawbacks and downward adjustments are strictly formalized as **signed net debits (`-$10,000`)** with unambiguous action codes (`CLAWBACK`).
- **What to Say to Evaluator:**
  > *"All compensating transactions use signed net debit semantics to ensure complete ledger clarity for regulatory audits."*

---

### Category 5: AI Copilot & API Ingestion

#### EC-11: Cloud LLM Outages & Hallucination (The Unreliable AI)
- **Plain English:** Using ChatGPT or Gemini to explain banking errors. What happens if the AI makes up a fake law, hallucinates a transaction, or the internet to OpenAI goes down?
- **The Danger:** Bank submits false audit reports to regulators, or audit tools freeze during an internet outage.
- **How TrustFork Handles It:**
  TrustFork’s Audit Copilot (`copilot.py`) uses **100% Deterministic Rule-Based Natural Language Generation**. It maps mathematical graph relations directly to certified English sentences. It runs in `<1 millisecond`, works completely offline, requires zero API keys, and has zero hallucination risk.
- **What to Say to Evaluator:**
  > *"In banking compliance, probabilistic LLMs are unacceptable. Our copilot uses deterministic finite-state semantic mapping to generate mathematically provable audit explanations."*

#### EC-12: Malformed or Negative Dollar Amounts (The Negative Loan)
- **Plain English:** An attacker submits a loan request for `-$5,000` hoping the bank's accounting system accidentally credits their account instead of debiting it.
- **The Danger:** Inverse accounting exploitation.
- **How TrustFork Handles It:**
  FastAPI and Pydantic schemas enforce positive integer boundaries (`gt=0`). Malformed requests are rejected at Gate 0 with an immediate `HTTP 422 Unprocessable Entity`.
- **What to Say to Evaluator:**
  > *"All API boundaries enforce strict Pydantic type and value constraints, rejecting negative or non-integer financial amounts before execution."*

---

### Category 6: Bounded Leases & The 5-Point Invariant

#### EC-13: Lease Parameter Inflation (The Forged Allowance)
- **Plain English:** A corrupt branch manager takes a signed lease for $15,000 and edits the file on disk to say $50,000.
- **The Danger:** The branch attempts to disburse $50,000 of the bank's funds.
- **How TrustFork Handles It:**
  The lease limit is part of the payload signed by Central's Ed25519 private key. Modifying `$15,000` to `$50,000` changes the canonical byte hash. At Gate 1, signature verification fails with `REJECTED_SIGNATURE`.
- **What to Say to Evaluator:**
  > *"The branch cannot forge Central's Ed25519 signature. Any parameter modification fails Gate 1 immediately."*

#### EC-14: Expired Lease / Time Warp (The Stale Voucher)
- **Plain English:** A branch tries to authorize a loan using a lease from last month whose validity has expired.
- **The Danger:** Authorizing transactions under outdated risk allowances.
- **How TrustFork Handles It:**
  Gate 3 checks the discrete **Logical Epoch**: `execution_epoch <= valid_until_epoch`. If the lease was only valid until Epoch 5, and the cluster is on Epoch 6, the transaction is rejected as `EXPIRED_LEASE`. Because epochs are integer counters, local PC clock tampering cannot bypass this.
- **What to Say to Evaluator:**
  > *"We enforce validity via discrete cluster governance epochs rather than physical wall clocks, eliminating NTP clock drift and client timestamp spoofing."*

#### EC-15: Scope Hijacking / Privilege Escalation (The Misused Budget)
- **Plain English:** A branch has a lease authorized for `LOAN_DISBURSEMENT` on `RETAIL_ACCOUNTS`, but attempts to use it to authorize a multi-million-dollar `DERIVATIVES_TRADE`.
- **The Danger:** Unauthorized high-risk operations disguised under low-risk leases.
- **How TrustFork Handles It:**
  Gate 4 verifies capability matching: the transaction's requested `action` and `resource` must match the lease's pre-approved scope. Mismatches are rejected with `SCOPE_MISMATCH`.
- **What to Say to Evaluator:**
  > *"Leases enforce the Principle of Least Privilege: authorizations are cryptographically bound to specific actions and resource domains."*

#### EC-16: Local Quota Overrun (The Empty Card)
- **Plain English:** A branch has a $15,000 lease. It has already disbursed $12,000. A customer walks in asking for $5,000.
- **The Danger:** Disbursing $5,000 would exceed the $15,000 cap by $2,000.
- **How TrustFork Handles It:**
  The branch's local edge engine checks `remaining_limit()` ($3,000). Because $5,000 > $3,000, the edge **fails closed locally**. The transaction is declined on the spot. No physical cash leaves the vault.
- **What to Say to Evaluator:**
  > *"The edge node enforces cumulative limits locally before opening the cash drawer. If remaining quota is insufficient, it fails closed immediately."*

---

## 5. Quick Defense Summary for Evaluators

If the evaluator asks: *"What is the overarching philosophy of your edge case handling?"*

Answer with these three sentences:
1. **At the Edge:** *"We fail-closed locally within pre-authorized cryptographic bounded leases so unauthorized funds are never disbursed."*
2. **At Reconciliation:** *"We enforce a deterministic 5-point invariant that guarantees all compliant edge transactions achieve permanent finality (`SURVIVES`) with zero clawbacks."*
3. **At the Safety Net:** *"For any un-leased legacy divergence, our durable SQLite Saga Orchestrator executes idempotent forward recovery so that the system never crashes or loses an audit trail."*
