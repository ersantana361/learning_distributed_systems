"""
Raft Leader Election Implementation

Leader election in Raft:
1. Follower becomes candidate after election timeout
2. Candidate increments term and votes for self
3. Candidate sends RequestVote to all peers
4. If majority votes received: become leader
5. If AppendEntries from valid leader: become follower
6. If election timeout: start new election

Key safety property: At most one leader per term

Related lectures: 6.1 Consensus, 6.2 Raft
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from node import RaftNode, NodeState
from log import LogEntry


@dataclass
class RequestVoteArgs:
    """Arguments for RequestVote RPC."""
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


@dataclass
class RequestVoteReply:
    """Reply for RequestVote RPC."""
    term: int
    vote_granted: bool


@dataclass
class AppendEntriesArgs:
    """Arguments for AppendEntries RPC."""
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int


@dataclass
class AppendEntriesReply:
    """Reply for AppendEntries RPC."""
    term: int
    success: bool
    match_index: int


class ElectionSimulator:
    """
    Simulates Raft election process for educational purposes.

    This is a synchronous simulation - in a real implementation,
    RPCs would be asynchronous and timeouts would be real timers.
    """

    def __init__(self, node_ids: List[str]):
        """Create a cluster of nodes."""
        self.nodes: Dict[str, RaftNode] = {}
        for node_id in node_ids:
            peers = [n for n in node_ids if n != node_id]
            self.nodes[node_id] = RaftNode(node_id, peers)

    def get_node(self, node_id: str) -> Optional[RaftNode]:
        return self.nodes.get(node_id)

    def request_vote(
        self,
        from_node: str,
        to_node: str,
        args: RequestVoteArgs
    ) -> Optional[RequestVoteReply]:
        """
        Simulate RequestVote RPC.

        Args:
            from_node: Candidate sending the request
            to_node: Node receiving the request
            args: RequestVote arguments

        Returns:
            RequestVoteReply or None if node unavailable
        """
        receiver = self.nodes.get(to_node)
        if receiver is None:
            return None

        term, granted = receiver.request_vote(
            args.term,
            args.candidate_id,
            args.last_log_index,
            args.last_log_term
        )
        return RequestVoteReply(term, granted)

    def append_entries(
        self,
        from_node: str,
        to_node: str,
        args: AppendEntriesArgs
    ) -> Optional[AppendEntriesReply]:
        """
        Simulate AppendEntries RPC.

        Args:
            from_node: Leader sending entries
            to_node: Follower receiving entries
            args: AppendEntries arguments

        Returns:
            AppendEntriesReply or None if node unavailable
        """
        receiver = self.nodes.get(to_node)
        if receiver is None:
            return None

        term, success, match_index = receiver.append_entries(
            args.term,
            args.leader_id,
            args.prev_log_index,
            args.prev_log_term,
            args.entries,
            args.leader_commit
        )
        return AppendEntriesReply(term, success, match_index)

    def run_election(self, candidate_id: str) -> bool:
        """
        Run a complete election for a candidate.

        Args:
            candidate_id: Node starting the election

        Returns:
            True if candidate won the election
        """
        candidate = self.nodes.get(candidate_id)
        if candidate is None:
            return False

        # Start election
        candidate.become_candidate()
        print(f"[{candidate_id}] Starting election for term {candidate.current_term}")

        # Prepare RequestVote args
        args = RequestVoteArgs(
            term=candidate.current_term,
            candidate_id=candidate_id,
            last_log_index=candidate.log.last_index(),
            last_log_term=candidate.log.last_term()
        )

        # Send RequestVote to all peers
        for peer_id in candidate.peers:
            reply = self.request_vote(candidate_id, peer_id, args)

            if reply is None:
                print(f"  [{candidate_id}] -> [{peer_id}]: No response (node unavailable)")
                continue

            print(f"  [{candidate_id}] -> [{peer_id}]: " +
                  f"term={reply.term}, granted={reply.vote_granted}")

            # Handle reply
            if reply.term > candidate.current_term:
                # Higher term discovered, step down
                candidate.become_follower(reply.term)
                print(f"  [{candidate_id}] Discovered higher term, becoming follower")
                return False

            if reply.vote_granted:
                candidate.votes_received.add(peer_id)

        # Check if won
        votes = len(candidate.votes_received)
        needed = candidate.quorum_size()
        print(f"  [{candidate_id}] Votes: {votes}/{needed} needed")

        if votes >= needed:
            candidate.become_leader()
            print(f"  [{candidate_id}] Won election! Became leader for term {candidate.current_term}")
            return True
        else:
            print(f"  [{candidate_id}] Lost election")
            return False

    def send_heartbeats(self, leader_id: str) -> Dict[str, bool]:
        """
        Leader sends heartbeats (empty AppendEntries) to all followers.

        Args:
            leader_id: The leader node

        Returns:
            Dict mapping peer_id to success
        """
        leader = self.nodes.get(leader_id)
        if leader is None or not leader.is_leader():
            return {}

        results = {}
        args = AppendEntriesArgs(
            term=leader.current_term,
            leader_id=leader_id,
            prev_log_index=leader.log.last_index(),
            prev_log_term=leader.log.last_term(),
            entries=[],  # Empty for heartbeat
            leader_commit=leader.volatile.commit_index
        )

        for peer_id in leader.peers:
            reply = self.append_entries(leader_id, peer_id, args)
            if reply:
                results[peer_id] = reply.success
                if reply.term > leader.current_term:
                    leader.become_follower(reply.term)
                    return results

        return results

    def get_leader(self) -> Optional[str]:
        """Find the current leader (if any)."""
        for node_id, node in self.nodes.items():
            if node.is_leader():
                return node_id
        return None

    def get_cluster_state(self) -> str:
        """Get a string representation of cluster state."""
        lines = ["Cluster State:"]
        for node_id, node in self.nodes.items():
            leader_marker = " *LEADER*" if node.is_leader() else ""
            lines.append(
                f"  {node_id}: state={node.state.value}, "
                f"term={node.current_term}, "
                f"voted_for={node.persistent.voted_for}, "
                f"log_len={len(node.log)}{leader_marker}"
            )
        return "\n".join(lines)


# Example usage and demonstration
if __name__ == "__main__":
    print("=== Raft Election Demonstration ===\n")

    # Create 5-node cluster
    sim = ElectionSimulator(["n1", "n2", "n3", "n4", "n5"])
    print(sim.get_cluster_state())

    # Node n1 starts election
    print("\n--- Election 1: n1 runs for leader ---")
    sim.run_election("n1")
    print()
    print(sim.get_cluster_state())

    # Leader sends heartbeats
    print("\n--- Leader sends heartbeats ---")
    results = sim.send_heartbeats("n1")
    print(f"Heartbeat results: {results}")

    # Simulate leader failure: n2 starts new election
    print("\n--- Election 2: n1 'fails', n2 runs for leader ---")
    # First, n2 must have higher term to win
    sim.nodes["n2"].persistent.current_term = sim.nodes["n1"].current_term
    sim.run_election("n2")
    print()
    print(sim.get_cluster_state())

    # Demonstrate split vote scenario
    print("\n=== Split Vote Scenario ===")
    sim2 = ElectionSimulator(["a", "b", "c", "d"])

    # a and b both start elections simultaneously
    sim2.nodes["a"].become_candidate()
    sim2.nodes["b"].become_candidate()

    print("Both a and b are candidates in same term!")
    print(f"  a: term={sim2.nodes['a'].current_term}")
    print(f"  b: term={sim2.nodes['b'].current_term}")

    # Each votes for themselves, others split
    # a gets vote from c
    sim2.nodes["c"].request_vote(
        sim2.nodes["a"].current_term, "a",
        sim2.nodes["a"].log.last_index(),
        sim2.nodes["a"].log.last_term()
    )
    sim2.nodes["a"].votes_received.add("c")

    # b gets vote from d
    sim2.nodes["d"].request_vote(
        sim2.nodes["b"].current_term, "b",
        sim2.nodes["b"].log.last_index(),
        sim2.nodes["b"].log.last_term()
    )
    sim2.nodes["b"].votes_received.add("d")

    print(f"\nVotes: a={len(sim2.nodes['a'].votes_received)}, " +
          f"b={len(sim2.nodes['b'].votes_received)}")
    print("Neither has majority (need 3 of 4) - election fails!")
    print("In real Raft, randomized election timeouts prevent this")
