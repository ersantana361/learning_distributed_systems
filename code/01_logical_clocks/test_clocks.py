"""
Tests for Lamport and Vector Clock implementations.
"""

import pytest
from lamport_clock import LamportClock, compare_timestamps
from vector_clock import VectorClock, CausalRelation


class TestLamportClock:
    """Tests for Lamport Clock implementation."""

    def test_initial_time_is_zero(self):
        clock = LamportClock("node1")
        assert clock.time == 0

    def test_tick_increments_time(self):
        clock = LamportClock("node1")
        clock.tick()
        assert clock.time == 1
        clock.tick()
        assert clock.time == 2

    def test_send_increments_and_returns_timestamp(self):
        clock = LamportClock("node1")
        ts, node_id = clock.send()
        assert ts == 1
        assert node_id == "node1"
        assert clock.time == 1

    def test_receive_updates_to_max_plus_one(self):
        clock = LamportClock("node1")
        clock.tick()  # local time = 1

        # Receive message with smaller timestamp
        clock.receive(0)
        assert clock.time == 2  # max(1, 0) + 1

        # Receive message with larger timestamp
        clock.receive(10)
        assert clock.time == 11  # max(2, 10) + 1

    def test_causality_preserved_through_messages(self):
        alice = LamportClock("alice")
        bob = LamportClock("bob")

        # Alice sends to Bob
        ts_send, _ = alice.send()
        ts_recv = bob.receive(ts_send)

        # Receive event must have larger timestamp than send event
        assert ts_recv > ts_send

    def test_compare_timestamps_ordering(self):
        # Different times
        assert compare_timestamps((1, "a"), (2, "a")) == -1
        assert compare_timestamps((2, "a"), (1, "a")) == 1

        # Same time, different nodes (tiebreaker)
        assert compare_timestamps((1, "a"), (1, "b")) == -1
        assert compare_timestamps((1, "b"), (1, "a")) == 1

        # Equal
        assert compare_timestamps((1, "a"), (1, "a")) == 0


class TestVectorClock:
    """Tests for Vector Clock implementation."""

    def test_initial_vector_has_own_entry(self):
        clock = VectorClock("node1")
        assert "node1" in clock.clock
        assert clock.clock["node1"] == 0

    def test_tick_increments_own_entry(self):
        clock = VectorClock("node1")
        clock.tick()
        assert clock.clock["node1"] == 1
        clock.tick()
        assert clock.clock["node1"] == 2

    def test_send_returns_copy(self):
        clock = VectorClock("node1")
        vc = clock.send()
        # Modify returned value shouldn't affect internal state
        vc["node1"] = 999
        assert clock.clock["node1"] == 1

    def test_receive_merges_and_increments(self):
        clock = VectorClock("node1")
        clock.tick()  # node1: 1

        # Receive message with different node's time
        clock.receive({"node2": 3})

        assert clock.clock["node1"] == 2  # incremented for receive
        assert clock.clock["node2"] == 3  # merged from message

    def test_receive_takes_max_of_each_component(self):
        clock = VectorClock("node1")
        clock.clock = {"node1": 5, "node2": 3}

        clock.receive({"node1": 2, "node2": 7, "node3": 1})

        assert clock.clock["node1"] == 6  # max(5, 2) + 1 for receive
        assert clock.clock["node2"] == 7  # max(3, 7)
        assert clock.clock["node3"] == 1  # from message

    def test_compare_equal(self):
        vc1 = {"a": 1, "b": 2}
        vc2 = {"a": 1, "b": 2}
        assert VectorClock.compare(vc1, vc2) == CausalRelation.EQUAL

    def test_compare_before(self):
        vc1 = {"a": 1, "b": 2}
        vc2 = {"a": 2, "b": 2}
        assert VectorClock.compare(vc1, vc2) == CausalRelation.BEFORE

    def test_compare_after(self):
        vc1 = {"a": 2, "b": 2}
        vc2 = {"a": 1, "b": 2}
        assert VectorClock.compare(vc1, vc2) == CausalRelation.AFTER

    def test_compare_concurrent(self):
        vc1 = {"a": 2, "b": 1}
        vc2 = {"a": 1, "b": 2}
        assert VectorClock.compare(vc1, vc2) == CausalRelation.CONCURRENT

    def test_compare_with_missing_entries(self):
        # Missing entries treated as 0
        vc1 = {"a": 1}
        vc2 = {"a": 1, "b": 1}
        # vc1[b] = 0 < vc2[b] = 1, so vc1 is before vc2
        assert VectorClock.compare(vc1, vc2) == CausalRelation.BEFORE

    def test_merge_takes_max(self):
        vc1 = {"a": 3, "b": 1}
        vc2 = {"a": 1, "b": 5, "c": 2}
        merged = VectorClock.merge(vc1, vc2)

        assert merged["a"] == 3
        assert merged["b"] == 5
        assert merged["c"] == 2

    def test_is_concurrent(self):
        vc1 = {"a": 2, "b": 1}
        vc2 = {"a": 1, "b": 2}
        assert VectorClock.is_concurrent(vc1, vc2) is True

        vc3 = {"a": 1, "b": 1}
        vc4 = {"a": 2, "b": 2}
        assert VectorClock.is_concurrent(vc3, vc4) is False

    def test_happens_before(self):
        vc1 = {"a": 1, "b": 1}
        vc2 = {"a": 2, "b": 2}
        assert VectorClock.happens_before(vc1, vc2) is True
        assert VectorClock.happens_before(vc2, vc1) is False

    def test_causality_through_message_chain(self):
        """Test that causality is properly tracked through message passing."""
        alice = VectorClock("alice")
        bob = VectorClock("bob")
        carol = VectorClock("carol")

        # Alice -> Bob -> Carol message chain
        msg1 = alice.send()
        bob.receive(msg1)

        msg2 = bob.send()
        carol.receive(msg2)

        # Carol's state should be causally after Alice's send
        assert VectorClock.happens_before(msg1, carol.get_time())

        # Alice does independent work
        alice.tick()

        # Alice's new state and Carol's state should be concurrent
        assert VectorClock.is_concurrent(alice.get_time(), carol.get_time())


class TestVectorClockConcurrencyDetection:
    """
    Tests specifically for the key advantage of vector clocks over Lamport:
    detecting concurrent events.
    """

    def test_detect_concurrent_updates(self):
        """
        Simulate two replicas making concurrent updates.
        Vector clocks should detect this as concurrent, not ordered.
        """
        replica1 = VectorClock("r1")
        replica2 = VectorClock("r2")

        # Both replicas start from same state
        # (imagine they both received the same initial sync)

        # Replica 1 makes an update
        replica1.tick()
        r1_state = replica1.get_time()

        # Replica 2 makes an update (without seeing R1's update)
        replica2.tick()
        r2_state = replica2.get_time()

        # These should be detected as concurrent
        assert VectorClock.is_concurrent(r1_state, r2_state)

    def test_distinguish_concurrent_from_causal(self):
        """
        Show that vector clocks can distinguish concurrent events
        from causally related events - something Lamport clocks cannot do.
        """
        node_a = VectorClock("A")
        node_b = VectorClock("B")

        # Causal chain: A sends to B
        msg = node_a.send()
        node_b.receive(msg)

        state_after_msg = node_b.get_time()

        # B's state is causally after A's send
        relation_causal = VectorClock.compare(msg, state_after_msg)
        assert relation_causal == CausalRelation.BEFORE

        # Now A does independent work
        node_a.tick()
        state_independent = node_a.get_time()

        # A's new state and B's state are concurrent
        relation_concurrent = VectorClock.compare(state_independent, state_after_msg)
        assert relation_concurrent == CausalRelation.CONCURRENT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
