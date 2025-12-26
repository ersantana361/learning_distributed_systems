"""
Raft Node State Machine Implementation

A Raft node can be in one of three states:
- Follower: Passive, receives entries from leader
- Candidate: Seeking election to become leader
- Leader: Handles client requests, replicates log

State transitions:
- Follower -> Candidate: Election timeout, no heartbeat received
- Candidate -> Leader: Wins election (majority votes)
- Candidate -> Follower: Discovers higher term or loses election
- Leader -> Follower: Discovers higher term

Related lectures: 6.1 Consensus, 6.2 Raft
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
from log import RaftLog, LogEntry


class NodeState(Enum):
    """Possible states for a Raft node."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class PersistentState:
    """
    State that must persist across restarts.

    - current_term: Latest term server has seen
    - voted_for: Candidate that received vote in current term (or None)
    - log: Log entries
    """
    current_term: int = 0
    voted_for: Optional[str] = None
    log: RaftLog = field(default_factory=RaftLog)


@dataclass
class VolatileState:
    """
    State that can be reconstructed after restart.

    - commit_index: Highest log entry known to be committed
    - last_applied: Highest log entry applied to state machine
    """
    commit_index: int = 0
    last_applied: int = 0


@dataclass
class LeaderState:
    """
    State only maintained by leaders.

    - next_index: For each server, index of next log entry to send
    - match_index: For each server, highest log entry known to be replicated
    """
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)

    def initialize(self, peers: List[str], last_log_index: int):
        """Initialize leader state when becoming leader."""
        for peer in peers:
            self.next_index[peer] = last_log_index + 1
            self.match_index[peer] = 0


@dataclass
class RaftNode:
    """
    A single node in a Raft cluster.

    Implements the Raft state machine for leader election and log replication.
    """

    node_id: str
    peers: List[str]  # IDs of other nodes in cluster

    # Persistent state
    persistent: PersistentState = field(default_factory=PersistentState)

    # Volatile state
    volatile: VolatileState = field(default_factory=VolatileState)

    # Leader-only state
    leader_state: Optional[LeaderState] = None

    # Current role
    state: NodeState = NodeState.FOLLOWER

    # Voting state (for candidates)
    votes_received: Set[str] = field(default_factory=set)

    # Current leader (for redirecting clients)
    current_leader: Optional[str] = None

    # Callback for applying commands to state machine
    apply_callback: Optional[Callable[[Any], None]] = None

    @property
    def current_term(self) -> int:
        return self.persistent.current_term

    @property
    def log(self) -> RaftLog:
        return self.persistent.log

    def is_leader(self) -> bool:
        return self.state == NodeState.LEADER

    def quorum_size(self) -> int:
        """Minimum number of nodes needed for majority."""
        total_nodes = len(self.peers) + 1  # Including self
        return total_nodes // 2 + 1

    # ========== State Transitions ==========

    def become_follower(self, term: int, leader_id: Optional[str] = None):
        """
        Transition to follower state.

        Called when:
        - Discovering a higher term
        - Losing an election
        - Receiving AppendEntries from valid leader
        """
        self.state = NodeState.FOLLOWER
        self.persistent.current_term = term
        self.persistent.voted_for = None
        self.leader_state = None
        self.votes_received = set()
        if leader_id:
            self.current_leader = leader_id

    def become_candidate(self):
        """
        Transition to candidate state and start election.

        Called when election timeout fires while follower.
        """
        self.state = NodeState.CANDIDATE
        self.persistent.current_term += 1
        self.persistent.voted_for = self.node_id  # Vote for self
        self.votes_received = {self.node_id}
        self.current_leader = None

    def become_leader(self):
        """
        Transition to leader state.

        Called when winning election (receiving majority votes).
        """
        self.state = NodeState.LEADER
        self.current_leader = self.node_id
        self.leader_state = LeaderState()
        self.leader_state.initialize(self.peers, self.log.last_index())

        # Append no-op entry for the new term (ensures commitment)
        # This is an optimization that helps commit entries from previous terms
        self.log.append(self.current_term, command={"type": "no-op"})

    # ========== RequestVote RPC ==========

    def request_vote(
        self,
        candidate_term: int,
        candidate_id: str,
        last_log_index: int,
        last_log_term: int
    ) -> tuple[int, bool]:
        """
        Handle RequestVote RPC from a candidate.

        Args:
            candidate_term: Candidate's term
            candidate_id: Candidate's ID
            last_log_index: Index of candidate's last log entry
            last_log_term: Term of candidate's last log entry

        Returns:
            Tuple of (current_term, vote_granted)
        """
        # Rule: If candidate term < current term, reject
        if candidate_term < self.current_term:
            return self.current_term, False

        # Rule: If candidate term > current term, update term and become follower
        if candidate_term > self.current_term:
            self.become_follower(candidate_term)

        # Grant vote if:
        # 1. Haven't voted yet OR already voted for this candidate
        # 2. Candidate's log is at least as up-to-date as ours
        vote_granted = False

        can_vote = (
            self.persistent.voted_for is None or
            self.persistent.voted_for == candidate_id
        )

        log_up_to_date = self.log.is_up_to_date(last_log_index, last_log_term)

        if can_vote and log_up_to_date:
            self.persistent.voted_for = candidate_id
            vote_granted = True

        return self.current_term, vote_granted

    def receive_vote(self, voter_term: int, vote_granted: bool) -> bool:
        """
        Handle vote response while candidate.

        Args:
            voter_term: Voter's term
            vote_granted: Whether vote was granted

        Returns:
            True if we won the election
        """
        if self.state != NodeState.CANDIDATE:
            return False

        # If voter has higher term, become follower
        if voter_term > self.current_term:
            self.become_follower(voter_term)
            return False

        if vote_granted:
            # Track that we received a vote (simulate from a peer)
            # In real implementation, track which peer voted
            self.votes_received.add(f"voter_{len(self.votes_received)}")

        # Check if we have majority
        if len(self.votes_received) >= self.quorum_size():
            self.become_leader()
            return True

        return False

    # ========== AppendEntries RPC ==========

    def append_entries(
        self,
        leader_term: int,
        leader_id: str,
        prev_log_index: int,
        prev_log_term: int,
        entries: List[LogEntry],
        leader_commit: int
    ) -> tuple[int, bool, int]:
        """
        Handle AppendEntries RPC from leader.

        Args:
            leader_term: Leader's term
            leader_id: Leader's ID
            prev_log_index: Index of entry preceding new entries
            prev_log_term: Term of entry at prev_log_index
            entries: Entries to append (empty for heartbeat)
            leader_commit: Leader's commit index

        Returns:
            Tuple of (current_term, success, match_index)
        """
        # Rule: If leader term < current term, reject
        if leader_term < self.current_term:
            return self.current_term, False, 0

        # Valid AppendEntries from leader - reset election timeout
        # (In real implementation, this would reset a timer)

        # If leader term >= current term, accept leader
        if leader_term > self.current_term:
            self.become_follower(leader_term, leader_id)
        else:
            # Same term, but we might be candidate - step down
            if self.state == NodeState.CANDIDATE:
                self.become_follower(leader_term, leader_id)
            self.current_leader = leader_id

        # Try to append entries
        success, match_index = self.log.append_entries(
            prev_log_index, prev_log_term, entries
        )

        if success:
            # Update commit index
            if leader_commit > self.volatile.commit_index:
                new_commit = min(leader_commit, self.log.last_index())
                self._apply_committed_entries(new_commit)

        return self.current_term, success, match_index

    def _apply_committed_entries(self, new_commit_index: int):
        """Apply newly committed entries to state machine."""
        while self.volatile.last_applied < new_commit_index:
            self.volatile.last_applied += 1
            entry = self.log.get_entry(self.volatile.last_applied)
            if entry and entry.command and self.apply_callback:
                self.apply_callback(entry.command)
        self.volatile.commit_index = new_commit_index

    # ========== Client Operations (Leader Only) ==========

    def client_request(self, command: Any) -> tuple[bool, Optional[int]]:
        """
        Handle client request (leader only).

        Args:
            command: Command to execute

        Returns:
            Tuple of (accepted, log_index)
        """
        if not self.is_leader():
            return False, None

        entry = self.log.append(self.current_term, command)
        return True, entry.index

    def update_commit_index(self):
        """
        Update commit index based on replication progress.

        Called by leader after receiving AppendEntries responses.
        Commits entries replicated to a majority.
        """
        if not self.is_leader() or self.leader_state is None:
            return

        # Find the highest index replicated to a majority
        for n in range(self.log.last_index(), self.volatile.commit_index, -1):
            # Only commit entries from current term
            if self.log.get_term(n) != self.current_term:
                continue

            # Count replicas (including self)
            count = 1
            for peer in self.peers:
                if self.leader_state.match_index.get(peer, 0) >= n:
                    count += 1

            if count >= self.quorum_size():
                self._apply_committed_entries(n)
                break

    def __repr__(self) -> str:
        return (
            f"RaftNode({self.node_id}, state={self.state.value}, "
            f"term={self.current_term}, log_len={len(self.log)})"
        )


# Example usage
if __name__ == "__main__":
    print("=== Raft Node Demonstration ===\n")

    # Create a 3-node cluster
    nodes = {
        "node1": RaftNode("node1", ["node2", "node3"]),
        "node2": RaftNode("node2", ["node1", "node3"]),
        "node3": RaftNode("node3", ["node1", "node2"]),
    }

    print("Initial state:")
    for node in nodes.values():
        print(f"  {node}")

    # Node1 starts election
    print("\n--- Node1 starts election ---")
    nodes["node1"].become_candidate()
    print(f"Node1: {nodes['node1']}")

    # Node1 requests votes
    print("\nNode1 requests votes from peers:")
    for peer_id in ["node2", "node3"]:
        peer = nodes[peer_id]
        term, granted = peer.request_vote(
            candidate_term=nodes["node1"].current_term,
            candidate_id="node1",
            last_log_index=nodes["node1"].log.last_index(),
            last_log_term=nodes["node1"].log.last_term()
        )
        print(f"  {peer_id} responds: term={term}, granted={granted}")

        # Node1 receives the vote
        if granted:
            nodes["node1"].votes_received.add(peer_id)

    # Check if node1 won
    if len(nodes["node1"].votes_received) >= nodes["node1"].quorum_size():
        nodes["node1"].become_leader()
        print(f"\nNode1 won election: {nodes['node1']}")

    # Leader handles client request
    print("\n--- Leader handles client request ---")
    success, index = nodes["node1"].client_request({"type": "SET", "key": "x", "value": 1})
    print(f"Client request accepted: {success}, log index: {index}")
    print(f"Leader log: {nodes['node1'].log}")
