"""
Consistency Level Demonstration

Shows the trade-offs between different consistency configurations:
- ONE: Fast but may return stale data
- QUORUM: Balanced (R + W > N guarantees freshness)
- ALL: Strongest consistency but lowest availability

Related lectures: 5.2 Quorums, 7.2 Linearizability, 7.3 Eventual Consistency
"""

from quorum_system import QuorumSystem, ConsistencyLevel, VersionedValue


def demo_consistency_tradeoffs():
    """Demonstrate the consistency-availability trade-off."""
    print("=== Consistency vs Availability Trade-offs ===\n")

    configs = [
        ("ONE", 1, 1),
        ("QUORUM", 3, 3),
        ("ALL", 5, 5),
    ]

    for name, r, w in configs:
        print(f"--- {name} (R={r}, W={w}) ---")
        system = QuorumSystem(n_replicas=5, read_quorum=r, write_quorum=w)

        # Calculate properties
        overlap = r + w > 5
        write_tolerance = 5 - w  # How many failures can we tolerate for writes
        read_tolerance = 5 - r   # How many failures can we tolerate for reads

        print(f"  R + W > N: {overlap} (linearizable reads: {overlap})")
        print(f"  Write survives {write_tolerance} failures")
        print(f"  Read survives {read_tolerance} failures")
        print()


def demo_sloppy_quorum_concept():
    """
    Demonstrate the concept of sloppy quorums (conceptually).

    In a sloppy quorum:
    - When preferred replicas are unavailable, writes go to other nodes
    - These nodes hold "hinted handoff" data
    - When original nodes recover, data is transferred back

    This improves availability at the cost of consistency guarantees.
    """
    print("=== Sloppy Quorum Concept ===\n")

    print("Standard (Strict) Quorum:")
    print("  - Key X maps to replicas [R1, R2, R3]")
    print("  - If R1 is down, write to X fails (need 2 of [R1, R2, R3])")
    print()

    print("Sloppy Quorum:")
    print("  - Key X maps to replicas [R1, R2, R3]")
    print("  - If R1 is down, write goes to R4 instead (hint: 'for R1')")
    print("  - When R1 recovers, R4 sends the data to R1")
    print("  - Better availability, but R + W > N doesn't guarantee freshness!")
    print()

    # Simulate the concept
    print("Simulation:")
    system = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=2)

    # Normal write
    success, acks = system.write("key1", "value1")
    print(f"  Normal write: success={success}, acks={acks}")

    # Simulate 2 replicas down
    system.set_replica_availability(0, False)
    system.set_replica_availability(1, False)
    print("  Replicas 0 and 1 went down")

    # Write still succeeds (goes to available replicas)
    success, acks = system.write("key1", "value2")
    print(f"  Write during partial failure: success={success}, acks={acks}")

    # Show state
    print(f"  Replica states: {system.get_replica_states('key1')}")
    print("  Note: Replicas 0, 1 are stale (would need hinted handoff)")


def demo_read_your_writes():
    """
    Demonstrate the read-your-writes consistency pattern.

    A session-level guarantee that a client always sees its own writes.
    """
    print("\n=== Read Your Writes Pattern ===\n")

    system = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=2)

    print("Problem with R=2, W=2 (no overlap guarantee):")
    print("  1. Client writes value 'A' -> goes to replicas [0, 1]")
    print("  2. Client immediately reads -> might hit replicas [2, 3]")
    print("  3. Client sees old value (or nothing)!")
    print()

    print("Solutions:")
    print("  1. Increase quorums: R + W > N")
    print("  2. Sticky sessions: route client to same replicas")
    print("  3. Version tracking: client tracks last write version,")
    print("     rejects reads with older versions")
    print()

    # Demonstrate version tracking approach
    print("Version tracking demonstration:")

    # Write and remember version
    success, _ = system.write("key", "my_value")
    # In a real system, client would get the write version back
    expected_version = system.next_version - 1
    print(f"  Client writes 'my_value', expects version >= {expected_version}")

    # Read
    value, version, _ = system.read("key")
    if version >= expected_version:
        print(f"  Read returned version {version} >= {expected_version}: OK")
    else:
        print(f"  Read returned version {version} < {expected_version}: STALE, retry!")


def demo_monotonic_reads():
    """
    Demonstrate monotonic reads consistency pattern.

    Guarantees that if a client sees version X, they won't later see version < X.
    """
    print("\n=== Monotonic Reads Pattern ===\n")

    print("Problem:")
    print("  1. Read returns value at version 5")
    print("  2. Later read (from different replica) returns version 3")
    print("  3. Client sees time going backwards!")
    print()

    print("Solutions:")
    print("  1. Track highest version seen per key")
    print("  2. Reject/retry reads that return older versions")
    print("  3. Use vector clocks for more precise causality tracking")


def demo_linearizability_requirements():
    """
    Show what's needed for linearizable read/write operations.
    """
    print("\n=== Linearizability Requirements ===\n")

    print("For linearizable operations (appears as single copy):")
    print()
    print("  Option 1: Quorum overlap")
    print("    - R + W > N")
    print("    - Plus: read repair or anti-entropy")
    print()
    print("  Option 2: Consensus protocol")
    print("    - Use Paxos, Raft, etc.")
    print("    - All operations go through leader")
    print("    - Stronger guarantees, higher latency")
    print()

    # Demo quorum that achieves linearizability
    system = QuorumSystem.with_consistency(5, ConsistencyLevel.QUORUM)
    print(f"  Quorum config: N=5, R={system.read_quorum}, W={system.write_quorum}")
    print(f"  R + W = {system.read_quorum + system.write_quorum} > N = 5")
    print(f"  Linearizable: {system.quorum_overlap()}")

    # Perform operations
    system.write("x", 1)
    system.write("x", 2)
    value, _, _ = system.read("x")
    print(f"  After writes 1, 2: read returns {value}")
    print("  With quorum overlap, we're guaranteed to see the latest write")


if __name__ == "__main__":
    demo_consistency_tradeoffs()
    demo_sloppy_quorum_concept()
    demo_read_your_writes()
    demo_monotonic_reads()
    demo_linearizability_requirements()
