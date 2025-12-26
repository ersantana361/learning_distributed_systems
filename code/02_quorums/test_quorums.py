"""
Tests for Quorum System implementation.
"""

import pytest
from quorum_system import (
    QuorumSystem,
    ConsistencyLevel,
    Replica,
    VersionedValue,
)


class TestReplica:
    """Tests for individual replica behavior."""

    def test_write_new_key(self):
        replica = Replica("r1")
        success = replica.write("key", "value", 1, 0.0)
        assert success
        assert replica.data["key"].value == "value"
        assert replica.data["key"].version == 1

    def test_write_newer_version_accepted(self):
        replica = Replica("r1")
        replica.write("key", "old", 1, 0.0)
        success = replica.write("key", "new", 2, 1.0)
        assert success
        assert replica.data["key"].value == "new"

    def test_write_older_version_rejected(self):
        replica = Replica("r1")
        replica.write("key", "new", 2, 1.0)
        success = replica.write("key", "old", 1, 0.0)
        assert not success
        assert replica.data["key"].value == "new"

    def test_unavailable_replica_rejects_write(self):
        replica = Replica("r1", available=False)
        success = replica.write("key", "value", 1, 0.0)
        assert not success

    def test_unavailable_replica_returns_none_on_read(self):
        replica = Replica("r1")
        replica.write("key", "value", 1, 0.0)
        replica.available = False
        assert replica.read("key") is None


class TestQuorumSystem:
    """Tests for quorum system operations."""

    def test_create_with_replicas(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        assert len(system.replicas) == 5

    def test_create_with_consistency_level_one(self):
        system = QuorumSystem.with_consistency(5, ConsistencyLevel.ONE)
        assert system.read_quorum == 1
        assert system.write_quorum == 1

    def test_create_with_consistency_level_quorum(self):
        system = QuorumSystem.with_consistency(5, ConsistencyLevel.QUORUM)
        assert system.read_quorum == 3  # 5 // 2 + 1
        assert system.write_quorum == 3

    def test_create_with_consistency_level_all(self):
        system = QuorumSystem.with_consistency(5, ConsistencyLevel.ALL)
        assert system.read_quorum == 5
        assert system.write_quorum == 5

    def test_quorum_overlap_detection(self):
        # R + W > N
        system1 = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        assert system1.quorum_overlap() is True

        # R + W = N
        system2 = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=3)
        assert system2.quorum_overlap() is False

        # R + W < N
        system3 = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=2)
        assert system3.quorum_overlap() is False

    def test_write_success_with_quorum(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        success, acks = system.write("key", "value")
        assert success is True
        assert acks == 5  # All replicas available

    def test_write_success_with_failures(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        system.set_replica_availability(0, False)
        system.set_replica_availability(1, False)

        success, acks = system.write("key", "value")
        assert success is True
        assert acks == 3  # Only 3 replicas available

    def test_write_failure_too_many_unavailable(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        system.set_replica_availability(0, False)
        system.set_replica_availability(1, False)
        system.set_replica_availability(2, False)

        success, acks = system.write("key", "value")
        assert success is False
        assert acks == 2  # Only 2 replicas available, need 3

    def test_read_returns_latest_version(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)

        system.write("key", "first")
        system.write("key", "second")

        value, version, _ = system.read("key")
        assert value == "second"
        assert version == 2

    def test_read_fails_without_quorum(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)
        system.write("key", "value")

        # Make too many replicas unavailable
        for i in range(3):
            system.set_replica_availability(i, False)

        value, version, responses = system.read("key")
        assert value is None
        assert len(responses) < 3

    def test_version_incrementing(self):
        system = QuorumSystem(n_replicas=3, read_quorum=2, write_quorum=2)

        system.write("key", "a")
        system.write("key", "b")
        system.write("key", "c")

        _, version, _ = system.read("key")
        assert version == 3


class TestQuorumConsistency:
    """Tests demonstrating consistency properties."""

    def test_overlapping_quorums_see_latest(self):
        """With R + W > N, reads always see the latest write."""
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)

        # Write goes to at least 3 replicas
        system.write("key", "latest_value")

        # Read from at least 3 replicas - guaranteed overlap with write
        value, _, _ = system.read("key")
        assert value == "latest_value"

    def test_non_overlapping_quorums_may_miss_latest(self):
        """Without overlap, reads might miss recent writes."""
        system = QuorumSystem(n_replicas=5, read_quorum=2, write_quorum=2)

        # Manually create a scenario where read misses write
        # Write only to replicas 0, 1
        system.replicas[0].write("key", "old", 1, 0.0)
        system.replicas[1].write("key", "old", 1, 0.0)

        # Write newer value only to replicas 3, 4
        system.replicas[3].write("key", "new", 2, 1.0)
        system.replicas[4].write("key", "new", 2, 1.0)

        # Make replicas 3, 4 unavailable
        system.set_replica_availability(3, False)
        system.set_replica_availability(4, False)

        # Read can only see the old value
        value, version, _ = system.read("key")
        assert value == "old"
        assert version == 1


class TestReadRepair:
    """Tests for read repair functionality."""

    def test_read_repair_updates_stale_replicas(self):
        system = QuorumSystem(n_replicas=5, read_quorum=3, write_quorum=3)

        # Manually create inconsistent state
        for i, replica in enumerate(system.replicas):
            if i < 3:
                replica.write("key", "new", 2, 1.0)
            else:
                replica.write("key", "old", 1, 0.0)

        # Verify inconsistent state
        states = system.get_replica_states("key")
        versions = [v.version if v else 0 for v in states.values()]
        assert 1 in versions and 2 in versions

        # Perform read repair
        repaired = system.read_repair("key")

        # All replicas should now have version 2
        states = system.get_replica_states("key")
        versions = [v.version for v in states.values() if v]
        assert all(v == 2 for v in versions)
        assert repaired >= 2  # At least 2 replicas were repaired


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
