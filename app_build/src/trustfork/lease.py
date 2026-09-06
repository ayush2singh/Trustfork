import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from trustfork.receipt import ReceiptSigner

@dataclass
class AuthorizationLease:
    lease_id: str
    domain_id: str
    principal: str
    action: str
    resource: str
    policy_hash: str
    valid_until_epoch: int
    usage_limit: int
    used_amount: int = 0
    authority_signature: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "domain_id": self.domain_id,
            "principal": self.principal,
            "action": self.action,
            "resource": self.resource,
            "policy_hash": self.policy_hash,
            "valid_until_epoch": self.valid_until_epoch,
            "usage_limit": self.usage_limit
        }

    def canonical_bytes(self) -> bytes:
        return ReceiptSigner.canonicalize(self.to_payload())

    def verify_signature(self, authority_verify_key: VerifyKey) -> bool:
        if not self.authority_signature:
            return False
        try:
            sig = bytes.fromhex(self.authority_signature)
            authority_verify_key.verify(self.canonical_bytes(), sig)
            return True
        except (BadSignatureError, ValueError):
            return False

    def remaining_limit(self) -> int:
        return max(0, self.usage_limit - self.used_amount)

class LeaseAuthority:
    def __init__(self, authority_key: SigningKey):
        self.authority_key = authority_key

    def issue_lease(
        self,
        domain_id: str,
        action: str,
        resource: str,
        policy_hash: str,
        valid_until_epoch: int,
        usage_limit: int,
        principal: str = "*",
        lease_id: Optional[str] = None
    ) -> AuthorizationLease:
        lid = lease_id or f"LEASE-{domain_id.upper()}-{valid_until_epoch}"
        lease = AuthorizationLease(
            lease_id=lid,
            domain_id=domain_id,
            principal=principal,
            action=action,
            resource=resource,
            policy_hash=policy_hash,
            valid_until_epoch=valid_until_epoch,
            usage_limit=usage_limit
        )
        signed = self.authority_key.sign(lease.canonical_bytes())
        lease.authority_signature = signed.signature.hex()
        return lease

class LocalLeaseEvaluator:
    def __init__(self, domain_id: str, authority_verify_key: VerifyKey):
        self.domain_id = domain_id
        self.authority_verify_key = authority_verify_key
        self.lease: Optional[AuthorizationLease] = None

    def set_lease(self, lease: AuthorizationLease):
        self.lease = lease

    def evaluate(self, request: Dict[str, Any], current_epoch: int) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.lease:
            return False, "NO_ACTIVE_LEASE", {}
        if not self.lease.verify_signature(self.authority_verify_key):
            return False, "INVALID_LEASE_SIGNATURE", {}
        if self.lease.domain_id != self.domain_id:
            return False, "LEASE_DOMAIN_MISMATCH", {}
        if current_epoch > self.lease.valid_until_epoch:
            return False, "LEASE_EXPIRED", {
                "current_epoch": current_epoch,
                "valid_until_epoch": self.lease.valid_until_epoch
            }
        req_action = request.get("action", "")
        if req_action != self.lease.action:
            return False, "ACTION_OUTSIDE_LEASE_SCOPE", {"action": req_action, "expected": self.lease.action}
        amount = request.get("amount", 0)
        remaining = self.lease.remaining_limit()
        if amount > remaining:
            return False, "EXCEEDS_LEASE_USAGE_LIMIT", {
                "requested": amount,
                "remaining": remaining,
                "usage_limit": self.lease.usage_limit
            }
        self.lease.used_amount += amount
        return True, "ALLOWED_BY_LEASE", {
            "lease_id": self.lease.lease_id,
            "policy_hash": self.lease.policy_hash,
            "valid_until_epoch": self.lease.valid_until_epoch,
            "amount": amount,
            "remaining_limit": self.lease.remaining_limit()
        }

