# Learning Journal

## Confidently Understood Concepts
- Distributed authorization under network partitions: Understanding that offline nodes can sign authorizations that diverge from concurrent cluster decisions.
- Compensation pattern: When network reconnects and reconciliation detects a policy breach or fork, committed bank transactions must trigger compensating actions rather than pretending the offline event never happened.
- CI/CD target environment: Pinned explicitly to Python 3.12 to match the repository's `.python-version` and avoid matrix bloat.
- CI Failure Propagation: Confidently understands that unhandled exceptions in integration smoke scripts (`main.py`) return non-zero exit codes that fail the CI run (marking it red), serving as an integration safety net beyond isolated unit tests.

## Knowledge Gaps & Areas for Socratic Verification
- Merkle-DAG content-addressing mechanics: How `parent_hash` and canonical JSON hashing prevent policy tampering and enable decentralized fork detection.
- CRDT convergence semantics: How divergent policy branches are compared and resolved deterministically across peers.

