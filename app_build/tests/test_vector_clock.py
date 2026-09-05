from src.trustfork.vector_clock import VectorClock, CausalRelation

def test_happens_before():
    vc1 = {"HQ": 10, "Branch": 5}
    vc2 = {"HQ": 12, "Branch": 6}
    assert VectorClock.compare(vc1, vc2) == CausalRelation.HAPPENS_BEFORE

def test_happens_after():
    vc1 = {"HQ": 12, "Branch": 6}
    vc2 = {"HQ": 10, "Branch": 5}
    assert VectorClock.compare(vc1, vc2) == CausalRelation.HAPPENS_AFTER

def test_equal():
    vc1 = {"HQ": 10, "Branch": 5}
    vc2 = {"HQ": 10, "Branch": 5}
    assert VectorClock.compare(vc1, vc2) == CausalRelation.EQUAL

def test_concurrent():
    vc1 = {"HQ": 11, "Branch": 10}
    vc2 = {"HQ": 10, "Branch": 11}
    assert VectorClock.compare(vc1, vc2) == CausalRelation.CONCURRENT

def test_missing_keys():
    vc1 = {"HQ": 5}
    vc2 = {"HQ": 5, "Branch": 2}
    assert VectorClock.compare(vc1, vc2) == CausalRelation.HAPPENS_BEFORE
