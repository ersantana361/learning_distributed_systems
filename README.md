# Distributed Systems

A structured learning project based on **Martin Kleppmann's Distributed Systems lecture series** from Cambridge University.

## Overview

This course covers the fundamental concepts of distributed systems, from basic networking and RPC to advanced topics like consensus algorithms, consistency models, and Google's Spanner. The material is based on Kleppmann's Cambridge University lectures, available on YouTube.

**Instructor**: Martin Kleppmann
**Source**: [YouTube Playlist](https://www.youtube.com/playlist?list=PLeKd45zvjcDFUEv_ohr_HdUFe97RItdiB)
**Companion Book**: *Designing Data-Intensive Applications* by Martin Kleppmann

## Learning Objectives

By completing this course, you will understand:

- How distributed systems differ from single-node systems
- The fundamental impossibility results (Two Generals, FLP)
- Physical and logical time in distributed systems
- Broadcast protocols and ordering guarantees
- Replication strategies and quorum systems
- Consensus algorithms (Paxos, Raft)
- Consistency models (linearizability, eventual consistency)
- Real-world systems like Google Spanner

## Prerequisites

- Basic understanding of networking (TCP/IP, HTTP)
- Familiarity with concurrent programming concepts
- Some database knowledge is helpful but not required

## Course Structure

### Section 1: Introduction
| File | Topic | Description |
|------|-------|-------------|
| `1_1_introduction.md` | Introduction | Distributed systems overview, motivation, and challenges |
| `1_2_computer_networking.md` | Computer Networking | Network fundamentals, latency, packet loss, protocols |
| `1_3_remote_procedure_call.md` | RPC | Remote procedure calls, IDL, service interfaces, failures |

### Section 2: Models & Fault Tolerance
| File | Topic | Description |
|------|-------|-------------|
| `2_1_two_generals_problem.md` | Two Generals Problem | Impossibility of guaranteed consensus over unreliable channels |
| `2_2_byzantine_generals_problem.md` | Byzantine Generals | Byzantine faults, trust assumptions, BFT algorithms |
| `2_3_system_models.md` | System Models | Synchronous vs asynchronous, crash vs Byzantine failures |
| `2_4_fault_tolerance.md` | Fault Tolerance | Failure detection, redundancy, availability patterns |

### Section 3: Physical Time
| File | Topic | Description |
|------|-------|-------------|
| `3_1_physical_time.md` | Physical Time | Clocks, UTC, time sources, clock hardware |
| `3_2_clock_synchronisation.md` | Clock Synchronisation | NTP, clock drift, Cristian's algorithm, Berkeley algorithm |
| `3_3_causality_and_happens_before.md` | Causality & Happens-Before | Lamport's happens-before relation, concurrent events |

### Section 4: Logical Time & Broadcast
| File | Topic | Description |
|------|-------|-------------|
| `4_1_logical_time.md` | Logical Time | Lamport timestamps, vector clocks, version vectors |
| `4_2_broadcast_ordering.md` | Broadcast Ordering | FIFO, causal, total order broadcast guarantees |
| `4_3_broadcast_algorithms.md` | Broadcast Algorithms | Reliable broadcast, eager/gossip protocols |

### Section 5: Replication
| File | Topic | Description |
|------|-------|-------------|
| `5_1_replication.md` | Replication | Why replicate, leader-based vs leaderless, consistency |
| `5_2_quorums.md` | Quorums | Read/write quorums, availability vs consistency trade-offs |
| `5_3_state_machine_replication.md` | State Machine Replication | Deterministic execution, log-based replication |

### Section 6: Consensus
| File | Topic | Description |
|------|-------|-------------|
| `6_1_consensus.md` | Consensus | FLP impossibility, consensus properties, Paxos overview |
| `6_2_raft.md` | Raft | Leader election, log replication, commitment protocol |

### Section 7: Transactions & Consistency
| File | Topic | Description |
|------|-------|-------------|
| `7_1_two_phase_commit.md` | Two-Phase Commit | Atomic commit, coordinator role, blocking problems |
| `7_2_linearizability.md` | Linearizability | Strong consistency, atomic operations, cost of linearizability |
| `7_3_eventual_consistency.md` | Eventual Consistency | CAP theorem, CRDTs, conflict resolution strategies |

### Section 8: Advanced Topics
| File | Topic | Description |
|------|-------|-------------|
| `8_1_collaboration_software.md` | Collaboration Software | Operational transformation, CRDTs for collaborative editing |
| `8_2_googles_spanner.md` | Google's Spanner | TrueTime, globally distributed transactions, Spanner architecture |

## Progress Tracker

### Section 1: Introduction
- [ ] 1.1 Introduction
- [ ] 1.2 Computer Networking
- [ ] 1.3 Remote Procedure Call

### Section 2: Models & Fault Tolerance
- [ ] 2.1 Two Generals Problem
- [ ] 2.2 Byzantine Generals Problem
- [ ] 2.3 System Models
- [ ] 2.4 Fault Tolerance

### Section 3: Physical Time
- [ ] 3.1 Physical Time
- [ ] 3.2 Clock Synchronisation
- [ ] 3.3 Causality and Happens-Before

### Section 4: Logical Time & Broadcast
- [ ] 4.1 Logical Time
- [ ] 4.2 Broadcast Ordering
- [ ] 4.3 Broadcast Algorithms

### Section 5: Replication
- [ ] 5.1 Replication
- [ ] 5.2 Quorums
- [ ] 5.3 State Machine Replication

### Section 6: Consensus
- [ ] 6.1 Consensus
- [ ] 6.2 Raft

### Section 7: Transactions & Consistency
- [ ] 7.1 Two-Phase Commit
- [ ] 7.2 Linearizability
- [ ] 7.3 Eventual Consistency

### Section 8: Advanced Topics
- [ ] 8.1 Collaboration Software
- [ ] 8.2 Google's Spanner

## Companion Resources

### Books
- *Designing Data-Intensive Applications* - Martin Kleppmann
- *Distributed Systems* - Maarten van Steen & Andrew Tanenbaum (free PDF)

### Papers
- [Time, Clocks, and the Ordering of Events](https://lamport.azurewebsites.net/pubs/time-clocks.pdf) - Lamport (1978)
- [The Byzantine Generals Problem](https://lamport.azurewebsites.net/pubs/byz.pdf) - Lamport et al. (1982)
- [Impossibility of Distributed Consensus with One Faulty Process (FLP)](https://groups.csail.mit.edu/tds/papers/Lynch/jacm85.pdf) - Fischer, Lynch, Paterson (1985)
- [In Search of an Understandable Consensus Algorithm (Raft)](https://raft.github.io/raft.pdf) - Ongaro & Ousterhout (2014)
- [Spanner: Google's Globally-Distributed Database](https://research.google/pubs/pub39966/) - Corbett et al. (2012)

### Interactive Resources
- [Raft Visualization](https://raft.github.io/)
- [The Secret Lives of Data - Raft](http://thesecretlivesofdata.com/raft/)

## Project Structure

```
distributed_systems/
├── README.md                    # This file
├── 1_1_introduction.md          # Lecture notes (24 files)
├── ...
├── 8_2_googles_spanner.md
├── notes/                       # Personal annotations
│   ├── README.md                # How to use notes
│   ├── section_N_*.md           # Notes by section
│   └── questions.md             # Questions to revisit
└── code/                        # Hands-on Python implementations
    ├── README.md                # Setup and usage instructions
    ├── requirements.txt         # pytest, typing-extensions
    ├── 01_logical_clocks/       # Lamport & Vector clocks (Lecture 4.1)
    ├── 02_quorums/              # Quorum systems (Lecture 5.2)
    ├── 03_raft/                 # Raft consensus (Lecture 6.2)
    └── 04_crdts/                # CRDTs: G-Counter, PN-Counter, LWW (Lecture 7.3)
```

## Code Examples

The `code/` directory contains educational Python implementations of key distributed systems concepts:

| Module | Concepts | Related Lectures |
|--------|----------|------------------|
| `01_logical_clocks/` | Lamport clocks, Vector clocks, causality detection | 4.1 Logical Time |
| `02_quorums/` | Read/write quorums, R+W>N, consistency levels | 5.2 Quorums |
| `03_raft/` | Leader election, log replication, commitment | 6.2 Raft |
| `04_crdts/` | G-Counter, PN-Counter, LWW-Register, LWW-Set | 7.3 Eventual Consistency |

Run tests: `cd code && python -m pytest`

## License

Lecture content is based on Martin Kleppmann's publicly available course materials. Personal notes and code experiments are for educational purposes.
