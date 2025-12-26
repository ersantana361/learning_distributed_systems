"""
G-Counter (Grow-only Counter) CRDT Implementation

A G-Counter can only be incremented, never decremented.
Each node maintains its own count, and the total is the sum of all counts.

Key properties:
- Increment operation: always valid, no conflicts
- Merge operation: take max of each node's count (idempotent, commutative, associative)
- Value: sum of all node counts

This is the simplest CRDT and forms the basis for more complex ones like PN-Counter.

Related lectures: 7.3 Eventual Consistency, 8.1 Collaboration Software
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GCounter:
    """
    A Grow-only Counter that can be replicated across nodes.

    Each node maintains a separate count. The total value is the
    sum of all node counts. Merging takes the maximum of each
    node's count, making the operation idempotent.
    """

    node_id: str
    counts: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure own entry exists."""
        if self.node_id not in self.counts:
            self.counts[self.node_id] = 0

    def increment(self, amount: int = 1) -> int:
        """
        Increment this node's counter.

        Args:
            amount: How much to increment (must be positive)

        Returns:
            The new value of this node's count

        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("G-Counter can only be incremented by positive amounts")

        self.counts[self.node_id] = self.counts.get(self.node_id, 0) + amount
        return self.counts[self.node_id]

    def value(self) -> int:
        """
        Get the current total value of the counter.

        Returns:
            Sum of all node counts
        """
        return sum(self.counts.values())

    def merge(self, other: GCounter) -> GCounter:
        """
        Merge with another G-Counter.

        Takes the maximum count for each node, ensuring that:
        - All increments are preserved
        - The operation is idempotent (merge(a, a) = a)
        - The operation is commutative (merge(a, b) = merge(b, a))
        - The operation is associative (merge(merge(a, b), c) = merge(a, merge(b, c)))

        Args:
            other: Another G-Counter to merge with

        Returns:
            A new merged G-Counter
        """
        all_nodes = set(self.counts.keys()) | set(other.counts.keys())
        merged_counts = {
            node: max(self.counts.get(node, 0), other.counts.get(node, 0))
            for node in all_nodes
        }
        return GCounter(self.node_id, merged_counts)

    def merge_in_place(self, other: GCounter) -> None:
        """
        Merge another G-Counter into this one (mutating).

        Args:
            other: Another G-Counter to merge with
        """
        for node, count in other.counts.items():
            self.counts[node] = max(self.counts.get(node, 0), count)

    def local_count(self) -> int:
        """Get this node's local count."""
        return self.counts.get(self.node_id, 0)

    def get_state(self) -> Dict[str, int]:
        """Get the internal state for serialization."""
        return self.counts.copy()

    @classmethod
    def from_state(cls, node_id: str, state: Dict[str, int]) -> GCounter:
        """Create a G-Counter from serialized state."""
        return cls(node_id, state.copy())


# Example usage and demonstration
if __name__ == "__main__":
    print("=== G-Counter Demonstration ===\n")

    # Create counters on three nodes
    counter_a = GCounter("node_a")
    counter_b = GCounter("node_b")
    counter_c = GCounter("node_c")

    print("Initial state (all zeros):")
    print(f"  Node A: {counter_a.counts}, value = {counter_a.value()}")
    print(f"  Node B: {counter_b.counts}, value = {counter_b.value()}")
    print(f"  Node C: {counter_c.counts}, value = {counter_c.value()}")

    # Simulate concurrent increments
    print("\nConcurrent increments (no communication):")
    counter_a.increment(3)
    counter_b.increment(2)
    counter_c.increment(5)

    print(f"  Node A increments by 3: {counter_a.counts}")
    print(f"  Node B increments by 2: {counter_b.counts}")
    print(f"  Node C increments by 5: {counter_c.counts}")

    # Merge all counters
    print("\nMerging counters:")
    # A merges with B
    counter_a.merge_in_place(counter_b)
    print(f"  A merges with B: {counter_a.counts}, value = {counter_a.value()}")

    # A merges with C
    counter_a.merge_in_place(counter_c)
    print(f"  A merges with C: {counter_a.counts}, value = {counter_a.value()}")

    # Show that merge is idempotent
    print("\nDemonstrating idempotence (merge same state again):")
    counter_a.merge_in_place(counter_c)
    print(f"  A merges with C again: {counter_a.counts}, value = {counter_a.value()}")
    print("  Value unchanged - merge is idempotent!")

    # Demonstrate convergence
    print("\nDemonstrating convergence:")
    counter_b.merge_in_place(counter_a)
    counter_c.merge_in_place(counter_a)
    print(f"  All nodes after full sync:")
    print(f"    A: {counter_a.value()}")
    print(f"    B: {counter_b.value()}")
    print(f"    C: {counter_c.value()}")
    print("  All nodes converge to the same value!")
