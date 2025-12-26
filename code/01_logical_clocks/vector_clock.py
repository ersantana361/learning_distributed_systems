"""
Vector Clock Implementation

Vector clocks extend Lamport clocks to detect concurrent events.

Key properties:
- If A happens-before B, then V(A) < V(B) (same as Lamport)
- If V(A) < V(B), then A happens-before B (converse also true!)
- If neither V(A) < V(B) nor V(B) < V(A), events are concurrent

The bidirectional implication makes vector clocks more powerful than
Lamport clocks for reasoning about causality.

Related lectures: 4.1 Logical Time, 7.3 Eventual Consistency (CRDTs)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set
from enum import Enum


class CausalRelation(Enum):
    """Possible causal relationships between two events."""
    BEFORE = "before"      # A happened before B
    AFTER = "after"        # A happened after B
    CONCURRENT = "concurrent"  # A and B are concurrent
    EQUAL = "equal"        # Same event


@dataclass
class VectorClock:
    """
    A vector clock for a single node in a distributed system.

    The vector maintains a counter for each known node. The entry for
    node N represents the number of events at N that causally precede
    or include the current event.
    """

    node_id: str
    clock: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure own entry exists in the vector."""
        if self.node_id not in self.clock:
            self.clock[self.node_id] = 0

    def tick(self) -> Dict[str, int]:
        """
        Record a local event. Increments own counter.

        Returns:
            Copy of the vector clock after the event
        """
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        return self.clock.copy()

    def send(self) -> Dict[str, int]:
        """
        Prepare to send a message.

        Increments own counter and returns the vector to attach
        to the outgoing message.

        Returns:
            Copy of the vector clock to include in the message
        """
        self.tick()
        return self.clock.copy()

    def receive(self, msg_clock: Dict[str, int]) -> Dict[str, int]:
        """
        Receive a message with a vector clock.

        Merges the received vector with the local vector using
        element-wise maximum, then increments own counter for
        the receive event.

        Args:
            msg_clock: The vector clock from the received message

        Returns:
            Copy of the vector clock after receiving
        """
        # Merge: take element-wise maximum
        all_nodes = set(self.clock.keys()) | set(msg_clock.keys())
        for node in all_nodes:
            self.clock[node] = max(
                self.clock.get(node, 0),
                msg_clock.get(node, 0)
            )
        # Increment own counter for the receive event
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        return self.clock.copy()

    def get_time(self) -> Dict[str, int]:
        """Get a copy of the current vector clock."""
        return self.clock.copy()

    @staticmethod
    def compare(vc1: Dict[str, int], vc2: Dict[str, int]) -> CausalRelation:
        """
        Compare two vector clocks to determine causal relationship.

        vc1 < vc2 (BEFORE) iff:
            - For all nodes: vc1[node] <= vc2[node]
            - For at least one node: vc1[node] < vc2[node]

        vc1 > vc2 (AFTER) iff vc2 < vc1

        vc1 || vc2 (CONCURRENT) iff neither vc1 < vc2 nor vc2 < vc1

        Args:
            vc1: First vector clock
            vc2: Second vector clock

        Returns:
            CausalRelation indicating the relationship
        """
        all_nodes = set(vc1.keys()) | set(vc2.keys())

        less_or_equal = True  # All vc1[i] <= vc2[i]
        greater_or_equal = True  # All vc1[i] >= vc2[i]
        strictly_less = False  # At least one vc1[i] < vc2[i]
        strictly_greater = False  # At least one vc1[i] > vc2[i]

        for node in all_nodes:
            v1 = vc1.get(node, 0)
            v2 = vc2.get(node, 0)

            if v1 > v2:
                less_or_equal = False
                strictly_greater = True
            if v1 < v2:
                greater_or_equal = False
                strictly_less = True

        if less_or_equal and greater_or_equal:
            return CausalRelation.EQUAL
        elif less_or_equal and strictly_less:
            return CausalRelation.BEFORE
        elif greater_or_equal and strictly_greater:
            return CausalRelation.AFTER
        else:
            return CausalRelation.CONCURRENT

    @staticmethod
    def merge(vc1: Dict[str, int], vc2: Dict[str, int]) -> Dict[str, int]:
        """
        Merge two vector clocks by taking element-wise maximum.

        This is useful for operations like joins in version vectors.

        Args:
            vc1: First vector clock
            vc2: Second vector clock

        Returns:
            New vector clock with max of each component
        """
        all_nodes = set(vc1.keys()) | set(vc2.keys())
        return {
            node: max(vc1.get(node, 0), vc2.get(node, 0))
            for node in all_nodes
        }

    @staticmethod
    def is_concurrent(vc1: Dict[str, int], vc2: Dict[str, int]) -> bool:
        """Check if two vector clocks represent concurrent events."""
        return VectorClock.compare(vc1, vc2) == CausalRelation.CONCURRENT

    @staticmethod
    def happens_before(vc1: Dict[str, int], vc2: Dict[str, int]) -> bool:
        """Check if vc1 happened before vc2."""
        return VectorClock.compare(vc1, vc2) == CausalRelation.BEFORE


def format_vector(vc: Dict[str, int], nodes: list = None) -> str:
    """Format a vector clock for display."""
    if nodes is None:
        nodes = sorted(vc.keys())
    return "[" + ", ".join(f"{n}:{vc.get(n, 0)}" for n in nodes) + "]"


# Example usage and demonstration
if __name__ == "__main__":
    print("=== Vector Clock Demonstration ===\n")

    # Create three processes
    alice = VectorClock("alice")
    bob = VectorClock("bob")
    carol = VectorClock("carol")

    nodes = ["alice", "bob", "carol"]

    print("Initial state:")
    print(f"  Alice: {format_vector(alice.get_time(), nodes)}")
    print(f"  Bob:   {format_vector(bob.get_time(), nodes)}")
    print(f"  Carol: {format_vector(carol.get_time(), nodes)}\n")

    # Scenario demonstrating causality
    print("1. Alice does local work")
    alice.tick()
    print(f"   Alice: {format_vector(alice.get_time(), nodes)}")

    print("\n2. Alice sends message to Bob")
    msg1 = alice.send()
    print(f"   Message VC: {format_vector(msg1, nodes)}")

    print("\n3. Bob receives message from Alice")
    bob.receive(msg1)
    print(f"   Bob: {format_vector(bob.get_time(), nodes)}")

    print("\n4. Bob sends message to Carol")
    msg2 = bob.send()
    print(f"   Message VC: {format_vector(msg2, nodes)}")

    print("\n5. Carol receives message from Bob")
    carol.receive(msg2)
    print(f"   Carol: {format_vector(carol.get_time(), nodes)}")

    # Save Carol's state for comparison
    carol_state = carol.get_time()

    # Concurrent events
    print("\n=== Detecting Concurrent Events ===")
    print("Meanwhile, Alice does local work (no communication with Carol)...")
    alice.tick()
    alice_state = alice.get_time()
    print(f"Alice: {format_vector(alice_state, nodes)}")
    print(f"Carol: {format_vector(carol_state, nodes)}")

    relation = VectorClock.compare(alice_state, carol_state)
    print(f"\nRelation between Alice's and Carol's states: {relation.value}")
    print("Vector clocks CAN detect that these events are concurrent!")

    # Causality detection
    print("\n=== Causality Detection ===")
    print("Comparing Bob's message (msg2) to Carol's current state:")
    print(f"  msg2:  {format_vector(msg2, nodes)}")
    print(f"  Carol: {format_vector(carol_state, nodes)}")
    relation = VectorClock.compare(msg2, carol_state)
    print(f"  Relation: msg2 is {relation.value} Carol's state")
    print("  (msg2 happened before Carol received it)")

    # Demonstrate merging
    print("\n=== Merging Vector Clocks ===")
    print("If we merge Alice's and Carol's clocks:")
    merged = VectorClock.merge(alice_state, carol_state)
    print(f"  Alice:  {format_vector(alice_state, nodes)}")
    print(f"  Carol:  {format_vector(carol_state, nodes)}")
    print(f"  Merged: {format_vector(merged, nodes)}")
    print("  (Element-wise maximum captures combined causal history)")
