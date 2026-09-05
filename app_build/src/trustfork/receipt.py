import json
from typing import Dict, Any, Tuple
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

class ReceiptSigner:
    @staticmethod
    def canonicalize(payload: Dict[str, Any]) -> bytes:
        """Enforces RFC 8785 JSON canonicalization rules (UTF-8, sorted keys, no whitespace)."""
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    @classmethod
    def create_receipt(cls, payload: Dict[str, Any], signing_key: SigningKey) -> Dict[str, Any]:
        """Canonicalizes payload and signs it using Ed25519."""
        canonical_bytes = cls.canonicalize(payload)
        signed = signing_key.sign(canonical_bytes)
        return {
            "payload": payload,
            "signature": signed.signature.hex()
        }

    @classmethod
    def verify_receipt(cls, receipt: Dict[str, Any], verify_key: VerifyKey) -> bool:
        """Verifies Ed25519 signature over the canonicalized payload."""
        try:
            canonical_bytes = cls.canonicalize(receipt["payload"])
            signature = bytes.fromhex(receipt["signature"])
            verify_key.verify(canonical_bytes, signature)
            return True
        except (BadSignatureError, KeyError, ValueError):
            return False
