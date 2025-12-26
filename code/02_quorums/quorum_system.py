"""
Quorum System Implementation

Demonstrates read/write quorums for distributed storage.

Key concepts:
- N replicas store copies of data
- Write quorum W: minimum replicas that must acknowledge a write
- Read quorum R: minimum replicas that must respond to a read
- If R + W > N: guaranteed to see most recent write (overlap)
- If R + W <= N: may see stale data (no guaranteed overlap)

Related lectures: 5.2 Quorums, 7.2 Linearizability
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import random


@dataclass
class VersionedValue:
    """A value with a version number for conflict resolution."""
    value: Any
    version: int
    timestamp: float  # For debugging/visualization

    def __repr__(self):
        return f"v{self.version}:{self.value}"


class ConsistencyLevel(Enum):
    """Common consistency level configurations."""
    ONE = "one"           # R=1 or W=1 (fast but potentially inconsistent)
    QUORUM = "quorum"     # R=W=floor(N/2)+1 (balanced)
    ALL = "all"           # R=N or W=N (slowest but strongest)


@dataclass
class Replica:
    """
    A single replica in the quorum system.

    Stores key-value pairs with version numbers.
    """
    replica_id: str
    data: Dict[str, VersionedValue] = field(default_factory=dict)
    available: bool = True  # Can be set to False to simulate failures

    def write(self, key: str, value: Any, version: int, timestamp: float) -> bool:
        """
        Write a value if the version is newer than current.

        Returns True if write was accepted.
        """
        if not self.available:
            return False

        current = self.data.get(key)
        if current is None or version > current.version:
            self.data[key] = VersionedValue(value, version, timestamp)
            return True
        return False

    def read(self, key: str) -> Optional[VersionedValue]:
        """Read a value. Returns None if replica unavailable or key missing."""
        if not self.available:
            return None
        return self.data.get(key)


@dataclass
class QuorumSystem:
    """
    A quorum-based distributed storage system.

    Supports configurable read and write quorum sizes.
    """
    n_replicas: int
    read_quorum: int
    write_quorum: int
    replicas: List[Replica] = field(default_factory=list)
    next_version: int = 1

    def __post_init__(self):
        """Initialize replicas if not provided."""
        if not self.replicas:
            self.replicas = [
                Replica(f"replica_{i}")
                for i in range(self.n_replicas)
            ]

    @classmethod
    def with_consistency(cls, n: int, level: ConsistencyLevel) -> "QuorumSystem":
        """Create a QuorumSystem with a predefined consistency level."""
        if level == ConsistencyLevel.ONE:
            return cls(n, read_quorum=1, write_quorum=1)
        elif level == ConsistencyLevel.QUORUM:
            quorum = n // 2 + 1
            return cls(n, read_quorum=quorum, write_quorum=quorum)
        elif level == ConsistencyLevel.ALL:
            return cls(n, read_quorum=n, write_quorum=n)
        else:
            raise ValueError(f"Unknown consistency level: {level}")

    def quorum_overlap(self) -> bool:
        """Check if R + W > N (guarantees seeing latest write)."""
        return self.read_quorum + self.write_quorum > self.n_replicas

    def write(self, key: str, value: Any, timestamp: float = 0.0) -> Tuple[bool, int]:
        """
        Write a value to the quorum.

        Args:
            key: The key to write
            value: The value to write
            timestamp: Optional timestamp for ordering

        Returns:
            Tuple of (success, number of replicas that acknowledged)
        """
        version = self.next_version
        self.next_version += 1

        acks = 0
        for replica in self.replicas:
            if replica.write(key, value, version, timestamp):
                acks += 1

        success = acks >= self.write_quorum
        return success, acks

    def read(self, key: str) -> Tuple[Optional[Any], int, List[VersionedValue]]:
        """
        Read a value from the quorum.

        Returns the value with the highest version from responding replicas.

        Args:
            key: The key to read

        Returns:
            Tuple of (value, version, all_responses)
        """
        responses: List[VersionedValue] = []

        for replica in self.replicas:
            result = replica.read(key)
            if result is not None:
                responses.append(result)

        if len(responses) < self.read_quorum:
            # Not enough replicas responded
            return None, 0, responses

        # Return the value with highest version
        if responses:
            best = max(responses, key=lambda x: x.version)
            return best.value, best.version, responses
        return None, 0, responses

    def read_repair(self, key: str) -> int:
        """
        Perform read repair: propagate the latest value to stale replicas.

        Returns the number of replicas that were repaired.
        """
        # First, read from all available replicas
        responses: List[Tuple[Replica, Optional[VersionedValue]]] = []
        for replica in self.replicas:
            result = replica.read(key)
            responses.append((replica, result))

        # Find the latest version
        values = [r[1] for r in responses if r[1] is not None]
        if not values:
            return 0

        latest = max(values, key=lambda x: x.version)

        # Repair stale replicas
        repaired = 0
        for replica, current in responses:
            if replica.available:
                if current is None or current.version < latest.version:
                    replica.write(key, latest.value, latest.version, latest.timestamp)
                    repaired += 1

        return repaired

    def get_replica_states(self, key: str) -> Dict[str, Optional[VersionedValue]]:
        """Get the state of a key across all replicas (for debugging)."""
        return {
            r.replica_id: r.data.get(key)
            for r in self.replicas
        }

    def set_replica_availability(self, replica_idx: int, available: bool):
        """Set whether a replica is available (simulates failures)."""
        if 0 <= replica_idx < len(self.replicas):
            self.replicas[replica_idx].available = available


def demonstrate_quorum_overlap():
    """Demonstrate how R + W > N ensures consistency."""
    print("=== Quorum Overlap Demonstration ===\n")

    # Create system with 5 replicas, R=3, W=3 (overlap guaranteed)
    system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
    print(f"System: N={system.n_replicas}, R={system.read_quorum}, W={system.write_quorum}")
    print(f"R + W = {system.read_quorum + system.write_quorum} > N = {system.n_replicas}")
    print(f"Overlap guaranteed: {system.quorum_overlap()}\n")

    # Write a value
    success, acks = system.write("x", "first_value", timestamp=1.0)
    print(f"Write 'first_value': success={success}, acks={acks}")

    # Show replica states
    print(f"Replica states: {system.get_replica_states('x')}\n")

    # Simulate partial failure: make 2 replicas unavailable
    print("Simulating 2 replica failures...")
    system.set_replica_availability(3, False)
    system.set_replica_availability(4, False)

    # Write new value (only goes to 3 replicas)
    success, acks = system.write("x", "second_value", timestamp=2.0)
    print(f"Write 'second_value': success={success}, acks={acks}")
    print(f"Replica states: {system.get_replica_states('x')}\n")

    # Read - should still see latest value due to overlap
    value, version, responses = system.read("x")
    print(f"Read result: value='{value}', version={version}")
    print(f"Responses from replicas: {responses}")
    print("With R + W > N, we're guaranteed to read the latest write!")


def demonstrate_stale_reads():
    """Demonstrate how R + W <= N can lead to stale reads."""
    print("\n=== Stale Read Demonstration ===\n")

    # Create system with no guaranteed overlap
    system = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=2)
    print(f"System: N={system.n_replicas}, R={system.read_quorum}, W={system.write_quorum}")
    print(f"R + W = {system.read_quorum + system.write_quorum} <= N = {system.n_replicas}")
    print(f"Overlap guaranteed: {system.quorum_overlap()}\n")

    # Write to first 2 replicas only
    system.replicas[0].write("x", "value_a", 1, 1.0)
    system.replicas[1].write("x", "value_a", 1, 1.0)

    # Write different value to last 2 replicas
    system.replicas[3].write("x", "value_b", 2, 2.0)
    system.replicas[4].write("x", "value_b", 2, 2.0)

    print("Artificially created split state:")
    print(f"Replica states: {system.get_replica_states('x')}\n")

    # Reading from different subsets can give different results
    print("Depending on which replicas respond to read:")
    print("  - If we read from [0, 1]: get 'value_a' (stale!)")
    print("  - If we read from [3, 4]: get 'value_b' (latest)")
    print("  - If we read from [0, 3]: get 'value_b' (due to version comparison)")


# Example usage
if __name__ == "__main__":
    demonstrate_quorum_overlap()
    demonstrate_stale_reads()

    print("\n=== Interactive Example ===\n")

    # Standard quorum configuration
    qs = QuorumSystem.with_consistency(5, ConsistencyLevel.QUORUM)
    print(f"Created quorum system: N=5, R={qs.read_quorum}, W={qs.write_quorum}")

    # Perform operations
    qs.write("user:123", {"name": "Alice", "email": "alice@example.com"})
    value, version, _ = qs.read("user:123")
    print(f"Read user:123 -> {value} (version {version})")

    qs.write("user:123", {"name": "Alice", "email": "alice@newdomain.com"})
    value, version, _ = qs.read("user:123")
    print(f"After update -> {value} (version {version})")
