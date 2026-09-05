import hashlib
import json
from typing import Dict, List, Optional, Any

class PolicyNode:
    def __init__(self, policy_id: str, version: str, rules: List[Dict[str, Any]], parent_hash: Optional[str] = None):
        self.policy_id = policy_id
        self.version = version
        self.rules = rules
        self.parent_hash = parent_hash
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = {
            "policy_id": self.policy_id,
            "version": self.version,
            "rules": self.rules,
            "parent_hash": self.parent_hash
        }
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(canonical_bytes).hexdigest()

    def evaluate(self, context: Dict[str, Any]) -> str:
        for rule in self.rules:
            if rule.get("action") == context.get("action"):
                max_amount = rule.get("max_amount")
                amount = context.get("amount", 0)
                if max_amount is None or amount <= max_amount:
                    return rule.get("effect", "DENY")
        return "DENY"

    def get_compensation_mapping(self, action: str) -> Optional[str]:
        for rule in self.rules:
            if rule.get("action") == action:
                return rule.get("compensation")
        return None

class MerklePolicyDAG:
    def __init__(self):
        self.nodes: Dict[str, PolicyNode] = {}
        self.tip_hash: Optional[str] = None

    def add_policy(self, policy: PolicyNode) -> str:
        self.nodes[policy.hash] = policy
        self.tip_hash = policy.hash
        return policy.hash

    def get_policy(self, policy_hash: str) -> Optional[PolicyNode]:
        return self.nodes.get(policy_hash)
