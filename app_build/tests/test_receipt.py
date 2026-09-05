from nacl.signing import SigningKey
from src.trustfork.receipt import ReceiptSigner

def test_sign_and_verify():
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    payload = {
        "receipt_id": "rcpt_001",
        "node_id": "Branch_B",
        "amount": 20000,
        "decision": "ALLOW"
    }

    receipt = ReceiptSigner.create_receipt(payload, signing_key)
    assert ReceiptSigner.verify_receipt(receipt, verify_key) is True

def test_tamper_detection():
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    payload = {
        "receipt_id": "rcpt_001",
        "node_id": "Branch_B",
        "amount": 20000,
        "decision": "ALLOW"
    }

    receipt = ReceiptSigner.create_receipt(payload, signing_key)

    # Tamper with payload
    receipt["payload"]["amount"] = 50000
    assert ReceiptSigner.verify_receipt(receipt, verify_key) is False

def test_canonical_key_order_invariance():
    # Demonstrating RFC 8785: key insertion order does not affect canonical bytes
    d1 = {"z": 1, "a": 2}
    d2 = {"a": 2, "z": 1}
    assert ReceiptSigner.canonicalize(d1) == ReceiptSigner.canonicalize(d2)
