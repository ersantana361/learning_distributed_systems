"""
LWW-Register (Last-Writer-Wins Register) CRDT Implementation

A LWW-Register stores a single value with a timestamp.
Concurrent writes are resolved by keeping the value with the latest timestamp.

Key properties:
- Simple conflict resolution: latest timestamp wins
- Requires synchronized clocks or logical timestamps
- Updates with older timestamps are discarded

Trade-offs:
- Simple and efficient
- May lose concurrent updates (only one survives)
- Clock synchronization issues can cause unexpected behavior

Related lectures: 7.3 Eventual Consistency, 8.1 Collaboration Software
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass
class LWWRegister:
    """
    A Last-Writer-Wins Register for storing a single value.

    Uses timestamps to resolve conflicts. The value with the
    highest timestamp always wins during merge.
    """

    node_id: str
    value: Any = None
    timestamp: float = 0.0

    def set(self, value: Any, timestamp: float) -> bool:
        """
        Set the value if the timestamp is newer than current.

        Args:
            value: The new value
            timestamp: The timestamp of this update

        Returns:
            True if the value was updated, False if timestamp was older
        """
        if timestamp > self.timestamp:
            self.value = value
            self.timestamp = timestamp
            return True
        elif timestamp == self.timestamp:
            # Tie-breaker: use value comparison (arbitrary but deterministic)
            # In practice, you might use node_id as tiebreaker
            if str(value) > str(self.value):
                self.value = value
                self.timestamp = timestamp
                return True
        return False

    def get(self) -> Tuple[Any, float]:
        """
        Get the current value and its timestamp.

        Returns:
            Tuple of (value, timestamp)
        """
        return (self.value, self.timestamp)

    def merge(self, other: LWWRegister) -> LWWRegister:
        """
        Merge with another LWW-Register.

        Takes the value with the highest timestamp.

        Args:
            other: Another LWW-Register to merge with

        Returns:
            A new merged LWW-Register
        """
        if other.timestamp > self.timestamp:
            return LWWRegister(self.node_id, other.value, other.timestamp)
        elif other.timestamp == self.timestamp:
            # Tie-breaker
            if str(other.value) > str(self.value):
                return LWWRegister(self.node_id, other.value, other.timestamp)
        return LWWRegister(self.node_id, self.value, self.timestamp)

    def merge_in_place(self, other: LWWRegister) -> bool:
        """
        Merge another LWW-Register into this one (mutating).

        Args:
            other: Another LWW-Register to merge with

        Returns:
            True if this register was updated
        """
        return self.set(other.value, other.timestamp)

    def get_state(self) -> Tuple[Any, float]:
        """Get the internal state for serialization."""
        return (self.value, self.timestamp)

    @classmethod
    def from_state(cls, node_id: str, value: Any, timestamp: float) -> LWWRegister:
        """Create an LWW-Register from serialized state."""
        return cls(node_id, value, timestamp)

    def __repr__(self) -> str:
        return f"LWWRegister(value={self.value!r}, ts={self.timestamp})"


@dataclass
class LWWRegisterWithBias:
    """
    LWW-Register with configurable bias for tie-breaking.

    When timestamps are equal, can bias toward:
    - "update": prefer the new value
    - "keep": prefer the existing value
    """

    node_id: str
    value: Any = None
    timestamp: float = 0.0
    bias: str = "update"  # "update" or "keep"

    def set(self, value: Any, timestamp: float) -> bool:
        """Set value using bias for tie-breaking."""
        if timestamp > self.timestamp:
            self.value = value
            self.timestamp = timestamp
            return True
        elif timestamp == self.timestamp and self.bias == "update":
            if value != self.value:
                self.value = value
                return True
        return False

    def get(self) -> Tuple[Any, float]:
        return (self.value, self.timestamp)


# Example usage and demonstration
if __name__ == "__main__":
    print("=== LWW-Register Demonstration ===\n")

    # Simulate a user profile that can be edited from multiple devices
    reg_phone = LWWRegister("phone")
    reg_laptop = LWWRegister("laptop")

    print("Scenario: User edits profile from phone and laptop")
    print()

    # Initial state: set from phone
    reg_phone.set({"name": "Alice", "status": "online"}, timestamp=1.0)
    print(f"1. Phone sets profile at t=1.0")
    print(f"   Phone: {reg_phone}")

    # Laptop sync (gets phone's state)
    reg_laptop.merge_in_place(reg_phone)
    print(f"\n2. Laptop syncs with phone")
    print(f"   Laptop: {reg_laptop}")

    # Concurrent updates: phone goes offline, laptop changes name
    reg_phone.set({"name": "Alice", "status": "offline"}, timestamp=2.0)
    reg_laptop.set({"name": "Alice Smith", "status": "online"}, timestamp=2.5)

    print(f"\n3. Concurrent updates (no sync yet)")
    print(f"   Phone (t=2.0): {reg_phone}")
    print(f"   Laptop (t=2.5): {reg_laptop}")

    # Merge - laptop wins (higher timestamp)
    reg_phone.merge_in_place(reg_laptop)
    print(f"\n4. Phone merges with laptop")
    print(f"   Phone: {reg_phone}")
    print("   Laptop's update wins (t=2.5 > t=2.0)")

    # Demonstrate timestamp conflicts
    print("\n=== Timestamp Conflict Demo ===")
    reg_a = LWWRegister("a")
    reg_b = LWWRegister("b")

    reg_a.set("value_A", timestamp=5.0)
    reg_b.set("value_B", timestamp=5.0)

    print(f"Same timestamp (5.0):")
    print(f"  Register A: {reg_a}")
    print(f"  Register B: {reg_b}")

    merged = reg_a.merge(reg_b)
    print(f"  Merged: {merged}")
    print("  Tie-breaker uses value comparison")

    # Show data loss scenario
    print("\n=== Data Loss Scenario ===")
    print("Problem: Concurrent writes with different timestamps")
    profile_1 = LWWRegister("r1")
    profile_2 = LWWRegister("r2")

    profile_1.set({"email": "new@email.com"}, timestamp=10.0)
    profile_2.set({"phone": "555-1234"}, timestamp=11.0)

    print(f"  Replica 1 updates email at t=10")
    print(f"  Replica 2 updates phone at t=11")

    profile_1.merge_in_place(profile_2)
    print(f"\n  After merge: {profile_1}")
    print("  Email update is LOST! Only phone update survives.")
    print("  LWW is simple but can lose concurrent updates.")
