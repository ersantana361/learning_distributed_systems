# Distributed Systems - Code Examples

Hands-on Python implementations of distributed systems concepts from Martin Kleppmann's lecture series.

## Setup

```bash
cd code
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running Examples

Each directory contains runnable examples and tests:

```bash
# Run a specific example
python 01_logical_clocks/lamport_clock.py

# Run tests for a module
pytest 01_logical_clocks/

# Run all tests
pytest
```

## Directory Structure

### 01_logical_clocks/
**Related lectures**: 4.1 Logical Time, 3.3 Causality

- `lamport_clock.py` - Lamport timestamps for total ordering
- `vector_clock.py` - Vector clocks for causal ordering & concurrency detection
- `test_clocks.py` - Unit tests

**Key concepts demonstrated**:
- Total ordering with Lamport clocks + node ID tiebreaker
- Causal ordering and happens-before relationship
- Detecting concurrent events with vector clocks

### 02_quorums/
**Related lectures**: 5.2 Quorums, 7.2 Linearizability

- `quorum_system.py` - Read/write quorum simulation
- `consistency_demo.py` - Demonstrate consistency levels
- `test_quorums.py` - Unit tests

**Key concepts demonstrated**:
- R + W > N for linearizability
- Stale reads when quorum overlap is insufficient
- Availability vs consistency trade-offs

### 03_raft/
**Related lectures**: 6.1 Consensus, 6.2 Raft

- `node.py` - Raft node state machine (Follower/Candidate/Leader)
- `log.py` - Replicated append-only log
- `election.py` - Leader election via RequestVote RPC
- `cluster.py` - Multi-node cluster simulation
- `test_raft.py` - Unit tests

**Key concepts demonstrated**:
- Leader election with term numbers
- Log replication and commitment
- Handling network partitions and leader failures

### 04_crdts/
**Related lectures**: 7.3 Eventual Consistency, 8.1 Collaboration Software

- `g_counter.py` - Grow-only counter
- `pn_counter.py` - Positive-negative counter (increment/decrement)
- `lww_register.py` - Last-writer-wins register
- `lww_set.py` - Last-writer-wins set
- `test_crdts.py` - Unit tests

**Key concepts demonstrated**:
- Conflict-free merge operations
- Strong eventual consistency
- Commutative and idempotent updates

### utils/
- `network_sim.py` - Simulated network with delays and partitions
- `visualization.py` - ASCII visualization helpers

## Design Philosophy

All implementations are:
- **From scratch** - No external distributed systems libraries
- **Educational** - Prioritize clarity over production optimizations
- **Testable** - Comprehensive unit tests for verification
- **Documented** - Inline comments explaining the "why"

## Further Exploration

After running these examples, try:
1. Modify parameters (quorum sizes, number of nodes)
2. Introduce failures and observe recovery
3. Visualize event ordering with timestamps
4. Compare CRDT merge results under different orderings
