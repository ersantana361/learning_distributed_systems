"""
Tests for Raft implementation.
"""

import pytest
from log import RaftLog, LogEntry
from node import RaftNode, NodeState
from election import ElectionSimulator, RequestVoteArgs


class TestRaftLog:
    """Tests for Raft log."""

    def test_initial_log_has_sentinel(self):
        log = RaftLog()
        assert len(log.entries) == 1
        assert log.entries[0].index == 0
        assert log.entries[0].term == 0

    def test_append_creates_entry(self):
        log = RaftLog()
        entry = log.append(term=1, command="SET x=1")
        assert entry.index == 1
        assert entry.term == 1
        assert entry.command == "SET x=1"

    def test_last_index_and_term(self):
        log = RaftLog()
        log.append(term=1, command="A")
        log.append(term=2, command="B")
        assert log.last_index() == 2
        assert log.last_term() == 2

    def test_append_entries_success(self):
        log = RaftLog()
        log.append(term=1, command="A")

        entries = [LogEntry(term=1, index=2, command="B")]
        success, match = log.append_entries(
            prev_log_index=1,
            prev_log_term=1,
            entries=entries
        )

        assert success is True
        assert match == 2
        assert len(log) == 2

    def test_append_entries_fails_missing_prev(self):
        log = RaftLog()
        # Log is empty, trying to append after index 1

        entries = [LogEntry(term=1, index=2, command="B")]
        success, _ = log.append_entries(
            prev_log_index=1,
            prev_log_term=1,
            entries=entries
        )

        assert success is False

    def test_append_entries_fails_term_mismatch(self):
        log = RaftLog()
        log.append(term=1, command="A")

        entries = [LogEntry(term=2, index=2, command="B")]
        success, _ = log.append_entries(
            prev_log_index=1,
            prev_log_term=2,  # Wrong term
            entries=entries
        )

        assert success is False

    def test_append_entries_truncates_conflicts(self):
        log = RaftLog()
        log.append(term=1, command="A")
        log.append(term=1, command="B_old")

        # Leader sends entry with different term at index 2
        entries = [LogEntry(term=2, index=2, command="B_new")]
        success, _ = log.append_entries(
            prev_log_index=1,
            prev_log_term=1,
            entries=entries
        )

        assert success is True
        assert log.get_entry(2).command == "B_new"
        assert log.get_entry(2).term == 2

    def test_commit(self):
        log = RaftLog()
        log.append(term=1, command="A")
        log.append(term=1, command="B")

        committed = log.commit(2)
        assert log.commit_index == 2
        assert committed == ["A", "B"]

    def test_is_up_to_date(self):
        log = RaftLog()
        log.append(term=1, command="A")
        log.append(term=2, command="B")

        # Higher term is more up-to-date
        assert log.is_up_to_date(last_log_index=1, last_log_term=3) is True

        # Same term, longer log is more up-to-date
        assert log.is_up_to_date(last_log_index=3, last_log_term=2) is True

        # Same term, same length
        assert log.is_up_to_date(last_log_index=2, last_log_term=2) is True

        # Shorter and older is not up-to-date
        assert log.is_up_to_date(last_log_index=1, last_log_term=1) is False


class TestRaftNode:
    """Tests for Raft node state machine."""

    def test_initial_state(self):
        node = RaftNode("n1", ["n2", "n3"])
        assert node.state == NodeState.FOLLOWER
        assert node.current_term == 0
        assert node.persistent.voted_for is None

    def test_become_candidate(self):
        node = RaftNode("n1", ["n2", "n3"])
        node.become_candidate()

        assert node.state == NodeState.CANDIDATE
        assert node.current_term == 1
        assert node.persistent.voted_for == "n1"
        assert "n1" in node.votes_received

    def test_become_leader(self):
        node = RaftNode("n1", ["n2", "n3"])
        node.become_candidate()
        node.votes_received.add("n2")  # Simulate receiving vote
        node.become_leader()

        assert node.state == NodeState.LEADER
        assert node.is_leader()
        assert node.leader_state is not None

    def test_become_follower(self):
        node = RaftNode("n1", ["n2", "n3"])
        node.become_candidate()
        node.become_follower(term=5, leader_id="n2")

        assert node.state == NodeState.FOLLOWER
        assert node.current_term == 5
        assert node.persistent.voted_for is None
        assert node.current_leader == "n2"

    def test_quorum_size(self):
        node3 = RaftNode("n1", ["n2", "n3"])
        assert node3.quorum_size() == 2  # 3 nodes, need 2

        node5 = RaftNode("n1", ["n2", "n3", "n4", "n5"])
        assert node5.quorum_size() == 3  # 5 nodes, need 3

    def test_request_vote_grants_vote(self):
        node = RaftNode("n1", ["n2"])

        term, granted = node.request_vote(
            candidate_term=1,
            candidate_id="n2",
            last_log_index=0,
            last_log_term=0
        )

        assert granted is True
        assert node.persistent.voted_for == "n2"

    def test_request_vote_rejects_older_term(self):
        node = RaftNode("n1", ["n2"])
        node.persistent.current_term = 5

        term, granted = node.request_vote(
            candidate_term=3,
            candidate_id="n2",
            last_log_index=0,
            last_log_term=0
        )

        assert granted is False

    def test_request_vote_rejects_if_already_voted(self):
        node = RaftNode("n1", ["n2", "n3"])
        node.persistent.current_term = 1
        node.persistent.voted_for = "n2"

        term, granted = node.request_vote(
            candidate_term=1,
            candidate_id="n3",  # Different candidate
            last_log_index=0,
            last_log_term=0
        )

        assert granted is False

    def test_request_vote_updates_term(self):
        node = RaftNode("n1", ["n2"])
        node.persistent.current_term = 1

        term, granted = node.request_vote(
            candidate_term=5,
            candidate_id="n2",
            last_log_index=0,
            last_log_term=0
        )

        assert node.current_term == 5
        assert granted is True

    def test_client_request_only_leader(self):
        follower = RaftNode("n1", ["n2"])
        success, index = follower.client_request({"cmd": "test"})
        assert success is False

        leader = RaftNode("n2", ["n1"])
        leader.become_candidate()
        leader.votes_received.add("n1")
        leader.become_leader()

        success, index = leader.client_request({"cmd": "test"})
        assert success is True
        assert index is not None


class TestElection:
    """Tests for leader election."""

    def test_election_success(self):
        sim = ElectionSimulator(["n1", "n2", "n3"])

        # n1 wins election
        won = sim.run_election("n1")

        assert won is True
        assert sim.nodes["n1"].is_leader()
        assert sim.get_leader() == "n1"

    def test_election_requires_majority(self):
        sim = ElectionSimulator(["n1", "n2", "n3", "n4", "n5"])

        # With 5 nodes, need 3 votes (including self)
        node = sim.nodes["n1"]
        node.become_candidate()

        # Only get one additional vote (self + 1 = 2, need 3)
        node.votes_received.add("n2")

        assert len(node.votes_received) < node.quorum_size()
        assert not node.is_leader()

    def test_higher_term_wins(self):
        sim = ElectionSimulator(["n1", "n2", "n3"])

        # n1 becomes leader in term 1
        sim.run_election("n1")
        assert sim.nodes["n1"].current_term == 1

        # n2 has higher term, should win
        sim.nodes["n2"].persistent.current_term = 2
        sim.run_election("n2")

        assert sim.get_leader() == "n2"
        assert sim.nodes["n2"].current_term == 3  # Incremented for election

    def test_follower_rejects_old_term(self):
        sim = ElectionSimulator(["n1", "n2"])

        # n2 has seen term 5
        sim.nodes["n2"].persistent.current_term = 5

        # n1 tries election with term 1
        args = RequestVoteArgs(
            term=1,
            candidate_id="n1",
            last_log_index=0,
            last_log_term=0
        )

        reply = sim.request_vote("n1", "n2", args)
        assert reply.vote_granted is False


class TestLogReplication:
    """Tests for log replication."""

    def test_leader_replicates_to_followers(self):
        sim = ElectionSimulator(["n1", "n2", "n3"])
        sim.run_election("n1")

        leader = sim.nodes["n1"]
        leader.client_request({"cmd": "SET x=1"})

        # First, replicate the no-op entry to establish consistency
        from election import AppendEntriesArgs

        # Send the no-op entry first (index 1)
        args_noop = AppendEntriesArgs(
            term=leader.current_term,
            leader_id="n1",
            prev_log_index=0,  # After sentinel
            prev_log_term=0,
            entries=leader.log.get_entries_from(1)[:1],  # Just no-op
            leader_commit=0
        )
        reply = sim.append_entries("n1", "n2", args_noop)
        assert reply.success is True

        # Now replicate the client command
        args = AppendEntriesArgs(
            term=leader.current_term,
            leader_id="n1",
            prev_log_index=1,  # After no-op
            prev_log_term=leader.current_term,
            entries=leader.log.get_entries_from(2),
            leader_commit=0
        )

        reply = sim.append_entries("n1", "n2", args)
        assert reply.success is True

        # n2 should have the entries
        assert sim.nodes["n2"].log.last_index() == leader.log.last_index()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
