from enum import Enum
from typing import Dict

class CausalRelation(str, Enum):
    HAPPENS_BEFORE = "HAPPENS_BEFORE"
    HAPPENS_AFTER = "HAPPENS_AFTER"
    EQUAL = "EQUAL"
    CONCURRENT = "CONCURRENT"

class VectorClock:
    def __init__(self, clock: Dict[str, int] = None):
        self.clock: Dict[str, int] = dict(clock) if clock else {}

    def increment(self, node_id: str) -> None:
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: "VectorClock") -> None:
        for node, val in other.clock.items():
            self.clock[node] = max(self.clock.get(node, 0), val)

    def to_dict(self) -> Dict[str, int]:
        return dict(self.clock)

    @classmethod
    def compare(cls, vc1: Dict[str, int], vc2: Dict[str, int]) -> CausalRelation:
        all_nodes = set(vc1.keys()).union(vc2.keys())
        less = False
        greater = False

        for node in all_nodes:
            val1 = vc1.get(node, 0)
            val2 = vc2.get(node, 0)
            if val1 < val2:
                less = True
            elif val1 > val2:
                greater = True

        if not less and not greater:
            return CausalRelation.EQUAL
        if less and not greater:
            return CausalRelation.HAPPENS_BEFORE
        if greater and not less:
            return CausalRelation.HAPPENS_AFTER
        return CausalRelation.CONCURRENT
