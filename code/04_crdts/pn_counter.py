"""
PN-Counter (Positive-Negative Counter) CRDT Implementation

A PN-Counter supports both increment and decrement operations by
using two G-Counters internally:
- P (positive): tracks increments
- N (negative): tracks decrements
- Value = P.value() - N.value()

Key properties:
- Both increment and decrement are conflict-free
- Merge combines both internal G-Counters
- The value can go negative

Related lectures: 7.3 Eventual Consistency, 8.1 Collaboration Software
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple
from g_counter import GCounter


@dataclass
class PNCounter:
    """
    A Positive-Negative Counter supporting both increment and decrement.

    Internally uses two G-Counters: one for increments (P) and one
    for decrements (N). The actual value is P - N.
    """

    node_id: str
    p_counter: GCounter = field(default=None)  # Positive (increments)
    n_counter: GCounter = field(default=None)  # Negative (decrements)

    def __post_init__(self):
        """Initialize internal counters if not provided."""
        if self.p_counter is None:
            self.p_counter = GCounter(self.node_id)
        if self.n_counter is None:
            self.n_counter = GCounter(self.node_id)

    def increment(self, amount: int = 1) -> int:
        """
        Increment the counter.

        Args:
            amount: How much to increment (must be positive)

        Returns:
            The new value of the counter
        """
        if amount <= 0:
            raise ValueError("Increment amount must be positive")
        self.p_counter.increment(amount)
        return self.value()

    def decrement(self, amount: int = 1) -> int:
        """
        Decrement the counter.

        Args:
            amount: How much to decrement (must be positive)

        Returns:
            The new value of the counter
        """
        if amount <= 0:
            raise ValueError("Decrement amount must be positive")
        self.n_counter.increment(amount)
        return self.value()

    def value(self) -> int:
        """
        Get the current value of the counter.

        Returns:
            P - N (can be negative)
        """
        return self.p_counter.value() - self.n_counter.value()

    def merge(self, other: PNCounter) -> PNCounter:
        """
        Merge with another PN-Counter.

        Merges both internal G-Counters independently.

        Args:
            other: Another PN-Counter to merge with

        Returns:
            A new merged PN-Counter
        """
        merged_p = self.p_counter.merge(other.p_counter)
        merged_n = self.n_counter.merge(other.n_counter)
        return PNCounter(self.node_id, merged_p, merged_n)

    def merge_in_place(self, other: PNCounter) -> None:
        """
        Merge another PN-Counter into this one (mutating).

        Args:
            other: Another PN-Counter to merge with
        """
        self.p_counter.merge_in_place(other.p_counter)
        self.n_counter.merge_in_place(other.n_counter)

    def get_state(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Get the internal state for serialization."""
        return (self.p_counter.get_state(), self.n_counter.get_state())

    @classmethod
    def from_state(
        cls,
        node_id: str,
        p_state: Dict[str, int],
        n_state: Dict[str, int]
    ) -> PNCounter:
        """Create a PN-Counter from serialized state."""
        return cls(
            node_id,
            GCounter.from_state(node_id, p_state),
            GCounter.from_state(node_id, n_state)
        )

    def __repr__(self) -> str:
        return f"PNCounter(value={self.value()}, P={self.p_counter.counts}, N={self.n_counter.counts})"


# Example usage and demonstration
if __name__ == "__main__":
    print("=== PN-Counter Demonstration ===\n")

    # Create counters on two nodes (e.g., like/dislike counter)
    counter_a = PNCounter("node_a")
    counter_b = PNCounter("node_b")

    print("Initial state:")
    print(f"  Node A: {counter_a}")
    print(f"  Node B: {counter_b}")

    # Node A: 3 likes
    print("\nNode A receives 3 likes:")
    counter_a.increment(3)
    print(f"  Node A: {counter_a}")

    # Node B: 1 like, 2 dislikes (concurrent with A)
    print("\nNode B receives 1 like and 2 dislikes (concurrent):")
    counter_b.increment(1)
    counter_b.decrement(2)
    print(f"  Node B: {counter_b}")

    # Merge
    print("\nMerging counters:")
    counter_a.merge_in_place(counter_b)
    print(f"  After merge at A: {counter_a}")
    print(f"  Value = {counter_a.p_counter.value()} - {counter_a.n_counter.value()} = {counter_a.value()}")

    # Show convergence
    counter_b.merge_in_place(counter_a)
    print(f"\nAfter full sync:")
    print(f"  Node A value: {counter_a.value()}")
    print(f"  Node B value: {counter_b.value()}")
    print("  Both nodes converge to the same value!")

    # Demonstrate negative values
    print("\n=== Negative Value Example ===")
    neg_counter = PNCounter("single")
    neg_counter.increment(2)
    neg_counter.decrement(5)
    print(f"  After +2, -5: value = {neg_counter.value()}")
