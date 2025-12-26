"""
Tests for CRDT implementations.
"""

import pytest
from g_counter import GCounter
from pn_counter import PNCounter
from lww_register import LWWRegister
from lww_set import LWWSet, Bias


class TestGCounter:
    """Tests for G-Counter."""

    def test_initial_value_is_zero(self):
        counter = GCounter("node1")
        assert counter.value() == 0

    def test_increment(self):
        counter = GCounter("node1")
        counter.increment(5)
        assert counter.value() == 5
        counter.increment(3)
        assert counter.value() == 8

    def test_increment_must_be_positive(self):
        counter = GCounter("node1")
        with pytest.raises(ValueError):
            counter.increment(0)
        with pytest.raises(ValueError):
            counter.increment(-1)

    def test_merge_takes_max(self):
        counter_a = GCounter("a")
        counter_b = GCounter("b")

        counter_a.increment(5)
        counter_b.increment(3)

        merged = counter_a.merge(counter_b)
        assert merged.value() == 8  # 5 + 3

    def test_merge_is_idempotent(self):
        counter_a = GCounter("a")
        counter_b = GCounter("b")

        counter_a.increment(5)
        counter_b.increment(3)

        merged1 = counter_a.merge(counter_b)
        merged2 = merged1.merge(counter_b)

        assert merged1.value() == merged2.value()

    def test_merge_is_commutative(self):
        counter_a = GCounter("a")
        counter_b = GCounter("b")

        counter_a.increment(5)
        counter_b.increment(3)

        ab = counter_a.merge(counter_b)
        ba = counter_b.merge(counter_a)

        assert ab.value() == ba.value()

    def test_merge_is_associative(self):
        counter_a = GCounter("a")
        counter_b = GCounter("b")
        counter_c = GCounter("c")

        counter_a.increment(5)
        counter_b.increment(3)
        counter_c.increment(7)

        # (a merge b) merge c
        ab_c = counter_a.merge(counter_b).merge(counter_c)

        # a merge (b merge c)
        a_bc = counter_a.merge(counter_b.merge(counter_c))

        assert ab_c.value() == a_bc.value()

    def test_convergence(self):
        """All replicas converge to same value after full sync."""
        counters = [GCounter(f"node{i}") for i in range(3)]

        # Different increments on each
        counters[0].increment(5)
        counters[1].increment(3)
        counters[2].increment(7)

        # Full sync
        for i, c in enumerate(counters):
            for j, other in enumerate(counters):
                if i != j:
                    c.merge_in_place(other)

        # All should have same value
        values = [c.value() for c in counters]
        assert all(v == 15 for v in values)


class TestPNCounter:
    """Tests for PN-Counter."""

    def test_initial_value_is_zero(self):
        counter = PNCounter("node1")
        assert counter.value() == 0

    def test_increment_and_decrement(self):
        counter = PNCounter("node1")
        counter.increment(5)
        assert counter.value() == 5
        counter.decrement(2)
        assert counter.value() == 3

    def test_negative_value(self):
        counter = PNCounter("node1")
        counter.decrement(5)
        assert counter.value() == -5

    def test_merge_preserves_all_operations(self):
        counter_a = PNCounter("a")
        counter_b = PNCounter("b")

        counter_a.increment(10)
        counter_b.decrement(3)

        counter_a.merge_in_place(counter_b)
        assert counter_a.value() == 7  # 10 - 3

    def test_convergence(self):
        counter_a = PNCounter("a")
        counter_b = PNCounter("b")

        # Concurrent updates
        counter_a.increment(5)
        counter_a.decrement(2)
        counter_b.increment(3)
        counter_b.decrement(1)

        # Sync
        counter_a.merge_in_place(counter_b)
        counter_b.merge_in_place(counter_a)

        assert counter_a.value() == counter_b.value()
        assert counter_a.value() == 5  # (5+3) - (2+1)


class TestLWWRegister:
    """Tests for LWW-Register."""

    def test_initial_value_is_none(self):
        reg = LWWRegister("node1")
        value, ts = reg.get()
        assert value is None
        assert ts == 0.0

    def test_set_updates_value(self):
        reg = LWWRegister("node1")
        reg.set("hello", 1.0)
        value, ts = reg.get()
        assert value == "hello"
        assert ts == 1.0

    def test_newer_timestamp_wins(self):
        reg = LWWRegister("node1")
        reg.set("old", 1.0)
        reg.set("new", 2.0)
        value, _ = reg.get()
        assert value == "new"

    def test_older_timestamp_rejected(self):
        reg = LWWRegister("node1")
        reg.set("new", 2.0)
        result = reg.set("old", 1.0)
        assert result is False
        value, _ = reg.get()
        assert value == "new"

    def test_merge_takes_latest(self):
        reg_a = LWWRegister("a")
        reg_b = LWWRegister("b")

        reg_a.set("value_a", 1.0)
        reg_b.set("value_b", 2.0)

        merged = reg_a.merge(reg_b)
        value, ts = merged.get()
        assert value == "value_b"
        assert ts == 2.0

    def test_merge_tie_uses_value_comparison(self):
        reg_a = LWWRegister("a")
        reg_b = LWWRegister("b")

        reg_a.set("aaa", 1.0)
        reg_b.set("zzz", 1.0)

        merged = reg_a.merge(reg_b)
        value, _ = merged.get()
        assert value == "zzz"  # "zzz" > "aaa"

    def test_convergence(self):
        reg_a = LWWRegister("a")
        reg_b = LWWRegister("b")

        reg_a.set("value_a", 1.0)
        reg_b.set("value_b", 2.0)

        reg_a.merge_in_place(reg_b)
        reg_b.merge_in_place(reg_a)

        assert reg_a.get() == reg_b.get()


class TestLWWSet:
    """Tests for LWW-Set."""

    def test_initial_set_is_empty(self):
        s = LWWSet("node1")
        assert s.value() == set()

    def test_add_element(self):
        s = LWWSet("node1")
        s.add("apple", 1.0)
        assert "apple" in s.value()

    def test_remove_element(self):
        s = LWWSet("node1")
        s.add("apple", 1.0)
        s.remove("apple", 2.0)
        assert "apple" not in s.value()

    def test_add_after_remove(self):
        s = LWWSet("node1")
        s.add("apple", 1.0)
        s.remove("apple", 2.0)
        s.add("apple", 3.0)
        assert "apple" in s.value()

    def test_remove_before_add_doesnt_matter(self):
        s = LWWSet("node1")
        s.remove("apple", 1.0)
        s.add("apple", 2.0)
        assert "apple" in s.value()

    def test_add_bias_on_tie(self):
        s = LWWSet("node1", bias=Bias.ADD)
        s.add("apple", 1.0)
        s.remove("apple", 1.0)
        assert "apple" in s.value()

    def test_remove_bias_on_tie(self):
        s = LWWSet("node1", bias=Bias.REMOVE)
        s.add("apple", 1.0)
        s.remove("apple", 1.0)
        assert "apple" not in s.value()

    def test_merge_combines_operations(self):
        set_a = LWWSet("a")
        set_b = LWWSet("b")

        set_a.add("apple", 1.0)
        set_a.add("banana", 2.0)
        set_b.add("orange", 1.5)
        set_b.remove("banana", 3.0)

        merged = set_a.merge(set_b)
        assert "apple" in merged.value()
        assert "orange" in merged.value()
        assert "banana" not in merged.value()  # removed at t=3.0

    def test_convergence(self):
        set_a = LWWSet("a")
        set_b = LWWSet("b")

        # Concurrent operations
        set_a.add("item1", 1.0)
        set_a.remove("item2", 2.0)
        set_b.add("item2", 1.0)
        set_b.remove("item1", 3.0)

        # Sync
        set_a.merge_in_place(set_b)
        set_b.merge_in_place(set_a)

        assert set_a.value() == set_b.value()
        # item1: add@1.0, remove@3.0 -> not in set
        # item2: add@1.0, remove@2.0 -> not in set
        assert set_a.value() == set()

    def test_contains_without_add(self):
        s = LWWSet("node1")
        assert s.contains("nonexistent") is False

    def test_remove_nonexistent_element(self):
        s = LWWSet("node1")
        s.remove("nonexistent", 1.0)
        assert "nonexistent" not in s.value()


class TestCRDTConvergence:
    """Tests for convergence properties across all CRDTs."""

    def test_g_counter_all_replicas_converge(self):
        """G-Counter: all replicas reach same state after sync."""
        replicas = [GCounter(f"r{i}") for i in range(5)]

        # Random increments on each
        increments = [3, 7, 2, 5, 1]
        for i, inc in enumerate(increments):
            replicas[i].increment(inc)

        # Full mesh sync
        for r in replicas:
            for other in replicas:
                r.merge_in_place(other)

        # All should equal sum of increments
        expected = sum(increments)
        assert all(r.value() == expected for r in replicas)

    def test_lww_set_add_remove_ordering(self):
        """LWW-Set: order of operations doesn't matter, only timestamps."""
        set1 = LWWSet("s1")
        set2 = LWWSet("s2")

        # Different order, same final timestamps
        set1.add("x", 1.0)
        set1.remove("x", 2.0)
        set1.add("x", 3.0)

        set2.remove("x", 2.0)
        set2.add("x", 3.0)
        set2.add("x", 1.0)

        assert set1.value() == set2.value()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
