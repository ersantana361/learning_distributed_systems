"""
Raft Cluster Simulation

Provides a complete simulation of a Raft cluster including:
- Leader election
- Log replication
- Commitment of entries
- Handling of failures

This is educational code demonstrating Raft concepts.
A production implementation would need:
- Asynchronous RPCs
- Persistent storage
- Real timers for election/heartbeat timeouts
- Network failure handling

Related lectures: 6.1 Consensus, 6.2 Raft
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from node import RaftNode, NodeState
from log import RaftLog, LogEntry
from election import (
    ElectionSimulator,
    RequestVoteArgs,
    AppendEntriesArgs,
    AppendEntriesReply,
)


@dataclass
class ClusterConfig:
    """Configuration for a Raft cluster."""
    node_ids: List[str]
    initial_leader: Optional[str] = None


class RaftCluster:
    """
    A simulated Raft cluster for educational purposes.

    Provides methods to:
    - Initialize the cluster
    - Run elections
    - Replicate log entries
    - Simulate failures
    - Query cluster state
    """

    def __init__(self, config: ClusterConfig):
        self.config = config
        self.simulator = ElectionSimulator(config.node_ids)
        self.failed_nodes: Set[str] = set()
        self.applied_commands: Dict[str, List[Any]] = {
            node_id: [] for node_id in config.node_ids
        }

        # Set up apply callbacks
        for node_id in config.node_ids:
            node = self.simulator.nodes[node_id]
            node.apply_callback = lambda cmd, nid=node_id: self._on_apply(nid, cmd)

        # Initialize leader if specified
        if config.initial_leader:
            self.simulator.run_election(config.initial_leader)

    def _on_apply(self, node_id: str, command: Any):
        """Callback when a command is applied to a node's state machine."""
        if command and command.get("type") != "no-op":
            self.applied_commands[node_id].append(command)

    def get_leader(self) -> Optional[str]:
        """Get the current leader."""
        return self.simulator.get_leader()

    def get_node(self, node_id: str) -> Optional[RaftNode]:
        """Get a node by ID."""
        if node_id in self.failed_nodes:
            return None
        return self.simulator.nodes.get(node_id)

    def fail_node(self, node_id: str):
        """Simulate a node failure."""
        self.failed_nodes.add(node_id)
        print(f"[CLUSTER] Node {node_id} failed")

    def recover_node(self, node_id: str):
        """Recover a failed node."""
        self.failed_nodes.discard(node_id)
        print(f"[CLUSTER] Node {node_id} recovered")

    def submit_command(self, command: Any) -> bool:
        """
        Submit a command to the cluster.

        The command is sent to the leader, who appends it to the log
        and replicates it to followers.

        Args:
            command: The command to execute

        Returns:
            True if command was accepted by leader
        """
        leader_id = self.get_leader()
        if leader_id is None or leader_id in self.failed_nodes:
            print("[CLUSTER] No available leader")
            return False

        leader = self.simulator.nodes[leader_id]
        success, index = leader.client_request(command)

        if success:
            print(f"[CLUSTER] Command accepted at index {index}")
        return success

    def replicate(self) -> Dict[str, bool]:
        """
        Replicate log entries from leader to followers.

        This simulates one round of AppendEntries RPCs.

        Returns:
            Dict mapping node_id to replication success
        """
        leader_id = self.get_leader()
        if leader_id is None:
            return {}

        leader = self.simulator.nodes[leader_id]
        if not leader.is_leader() or leader.leader_state is None:
            return {}

        results = {}

        for peer_id in leader.peers:
            if peer_id in self.failed_nodes:
                results[peer_id] = False
                continue

            peer = self.simulator.nodes.get(peer_id)
            if peer is None:
                results[peer_id] = False
                continue

            # Get entries to send
            next_idx = leader.leader_state.next_index.get(peer_id, 1)
            entries = leader.log.get_entries_from(next_idx)

            # Prepare AppendEntries
            prev_idx = next_idx - 1
            args = AppendEntriesArgs(
                term=leader.current_term,
                leader_id=leader_id,
                prev_log_index=prev_idx,
                prev_log_term=leader.log.get_term(prev_idx),
                entries=entries,
                leader_commit=leader.volatile.commit_index
            )

            # Send RPC
            reply = self.simulator.append_entries(leader_id, peer_id, args)

            if reply is None:
                results[peer_id] = False
                continue

            results[peer_id] = reply.success

            if reply.success:
                # Update next_index and match_index
                leader.leader_state.next_index[peer_id] = reply.match_index + 1
                leader.leader_state.match_index[peer_id] = reply.match_index
            else:
                # Decrement next_index and retry (simplified)
                leader.leader_state.next_index[peer_id] = max(1, next_idx - 1)

        # Update commit index
        leader.update_commit_index()

        return results

    def run_election(self, candidate_id: str) -> bool:
        """Run an election for a specific node."""
        if candidate_id in self.failed_nodes:
            return False
        return self.simulator.run_election(candidate_id)

    def get_status(self) -> str:
        """Get a formatted status string for the cluster."""
        lines = ["=" * 60, "CLUSTER STATUS", "=" * 60]

        leader = self.get_leader()
        lines.append(f"Leader: {leader or 'NONE'}")
        lines.append(f"Failed nodes: {self.failed_nodes or 'none'}")
        lines.append("")

        for node_id, node in self.simulator.nodes.items():
            status = "FAILED" if node_id in self.failed_nodes else node.state.value
            leader_mark = " *" if node_id == leader else ""
            lines.append(
                f"{node_id}{leader_mark}: "
                f"term={node.current_term}, "
                f"log={len(node.log)}, "
                f"commit={node.volatile.commit_index}, "
                f"status={status}"
            )

        lines.append("")
        lines.append("Applied commands per node:")
        for node_id, commands in self.applied_commands.items():
            lines.append(f"  {node_id}: {len(commands)} commands")

        return "\n".join(lines)


def demo_basic_replication():
    """Demonstrate basic log replication."""
    print("=== Basic Log Replication Demo ===\n")

    # Create 3-node cluster with n1 as leader
    cluster = RaftCluster(ClusterConfig(
        node_ids=["n1", "n2", "n3"],
        initial_leader="n1"
    ))

    print(cluster.get_status())

    # Submit some commands
    print("\n--- Submitting commands ---")
    cluster.submit_command({"op": "SET", "key": "x", "value": 1})
    cluster.submit_command({"op": "SET", "key": "y", "value": 2})

    # Replicate
    print("\n--- Replicating ---")
    results = cluster.replicate()
    print(f"Replication results: {results}")

    # Replicate again to commit
    results = cluster.replicate()

    print("\n" + cluster.get_status())


def demo_leader_failure():
    """Demonstrate leader failure and re-election."""
    print("\n" + "=" * 60)
    print("=== Leader Failure Demo ===\n")

    cluster = RaftCluster(ClusterConfig(
        node_ids=["n1", "n2", "n3", "n4", "n5"],
        initial_leader="n1"
    ))

    # Submit and replicate some commands
    cluster.submit_command({"op": "SET", "key": "x", "value": 1})
    cluster.replicate()
    cluster.replicate()

    print("Initial state:")
    print(cluster.get_status())

    # Fail the leader
    print("\n--- Leader n1 fails ---")
    cluster.fail_node("n1")

    # n2 starts election
    print("\n--- n2 runs for leader ---")
    cluster.run_election("n2")

    print("\n" + cluster.get_status())

    # Submit new command to new leader
    print("\n--- Submit command to new leader ---")
    cluster.submit_command({"op": "SET", "key": "y", "value": 2})
    cluster.replicate()
    cluster.replicate()

    print("\n" + cluster.get_status())


def demo_network_partition():
    """Demonstrate behavior during network partition."""
    print("\n" + "=" * 60)
    print("=== Network Partition Demo ===\n")

    cluster = RaftCluster(ClusterConfig(
        node_ids=["n1", "n2", "n3", "n4", "n5"],
        initial_leader="n1"
    ))

    # Submit initial command
    cluster.submit_command({"op": "SET", "key": "x", "value": 1})
    cluster.replicate()
    cluster.replicate()

    print("Before partition:")
    print(cluster.get_status())

    # Partition: n1 and n2 are isolated from n3, n4, n5
    print("\n--- Partition: n1, n2 isolated from n3, n4, n5 ---")
    # Simulate by failing n3, n4, n5 from n1's perspective
    # (In reality, this would be bidirectional network issues)

    # The minority partition (n1, n2) cannot commit
    # The majority partition (n3, n4, n5) can elect new leader
    cluster.fail_node("n1")  # Old leader isolated
    cluster.fail_node("n2")

    print("\n--- Majority partition elects n3 ---")
    cluster.run_election("n3")

    print("\n" + cluster.get_status())


# Example usage
if __name__ == "__main__":
    demo_basic_replication()
    demo_leader_failure()
    demo_network_partition()
