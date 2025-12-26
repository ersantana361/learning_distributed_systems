"""
Raft Replicated Log Implementation

The log is the core data structure in Raft. It stores commands that are
replicated across the cluster and applied to the state machine.

Key properties:
- Append-only (no modifications to committed entries)
- Each entry has: index, term, command
- Log Matching Property: If two logs have entry with same index and term,
  all preceding entries are identical

Related lectures: 6.1 Consensus, 6.2 Raft
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class LogEntry:
    """
    A single entry in the Raft log.

    Attributes:
        term: The term when this entry was created
        index: Position in the log (1-indexed)
        command: The command to apply to the state machine
    """
    term: int
    index: int
    command: Any

    def __repr__(self) -> str:
        return f"Entry(idx={self.index}, term={self.term}, cmd={self.command!r})"


@dataclass
class RaftLog:
    """
    The replicated log for a Raft node.

    Maintains entries and tracks commit progress.
    Index 0 is a sentinel (never used), actual entries start at index 1.
    """

    entries: List[LogEntry] = field(default_factory=list)
    commit_index: int = 0  # Highest index known to be committed

    def __post_init__(self):
        """Initialize with sentinel entry at index 0."""
        if not self.entries:
            # Sentinel entry at index 0
            self.entries = [LogEntry(term=0, index=0, command=None)]

    def last_index(self) -> int:
        """Get the index of the last log entry."""
        return len(self.entries) - 1

    def last_term(self) -> int:
        """Get the term of the last log entry."""
        return self.entries[-1].term if self.entries else 0

    def get_entry(self, index: int) -> Optional[LogEntry]:
        """Get the entry at a specific index."""
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None

    def get_term(self, index: int) -> int:
        """Get the term of the entry at index (0 if not exists)."""
        if 0 <= index < len(self.entries):
            return self.entries[index].term
        return 0

    def append(self, term: int, command: Any) -> LogEntry:
        """
        Append a new entry to the log.

        Args:
            term: The current term
            command: The command to store

        Returns:
            The newly created log entry
        """
        new_index = len(self.entries)
        entry = LogEntry(term=term, index=new_index, command=command)
        self.entries.append(entry)
        return entry

    def append_entries(
        self,
        prev_log_index: int,
        prev_log_term: int,
        entries: List[LogEntry]
    ) -> Tuple[bool, int]:
        """
        Append entries from leader (used in AppendEntries RPC).

        Implements the Log Matching safety property:
        1. Check if prev_log_index/term match
        2. Delete conflicting entries
        3. Append new entries

        Args:
            prev_log_index: Index of entry before new entries
            prev_log_term: Term of entry at prev_log_index
            entries: Entries to append

        Returns:
            Tuple of (success, match_index)
            - success: True if entries were appended
            - match_index: Highest index that matches leader's log
        """
        # Check if we have the entry at prev_log_index with correct term
        if prev_log_index > 0:
            if prev_log_index >= len(self.entries):
                # We don't have this entry yet
                return False, 0
            if self.entries[prev_log_index].term != prev_log_term:
                # Entry exists but term doesn't match - conflict
                return False, 0

        # Find where to start appending (handle conflicts)
        insert_index = prev_log_index + 1

        for i, entry in enumerate(entries):
            log_index = insert_index + i

            if log_index < len(self.entries):
                if self.entries[log_index].term != entry.term:
                    # Conflict: truncate log from this point
                    self.entries = self.entries[:log_index]
                    # Now append remaining entries
                    for remaining in entries[i:]:
                        self.entries.append(LogEntry(
                            term=remaining.term,
                            index=len(self.entries),
                            command=remaining.command
                        ))
                    break
                # Entry matches, continue
            else:
                # Append new entry
                self.entries.append(LogEntry(
                    term=entry.term,
                    index=len(self.entries),
                    command=entry.command
                ))

        match_index = self.last_index()
        return True, match_index

    def get_entries_from(self, start_index: int) -> List[LogEntry]:
        """Get all entries from start_index onwards."""
        if start_index < len(self.entries):
            return self.entries[start_index:]
        return []

    def commit(self, index: int) -> List[Any]:
        """
        Commit entries up to index.

        Args:
            index: The new commit index

        Returns:
            List of commands that were newly committed
        """
        if index <= self.commit_index:
            return []

        # Only commit if index is within our log
        new_commit_index = min(index, self.last_index())
        newly_committed = []

        for i in range(self.commit_index + 1, new_commit_index + 1):
            if self.entries[i].command is not None:
                newly_committed.append(self.entries[i].command)

        self.commit_index = new_commit_index
        return newly_committed

    def is_up_to_date(self, last_log_index: int, last_log_term: int) -> bool:
        """
        Check if a candidate's log is at least as up-to-date as ours.

        Used for voting decisions. A log is more up-to-date if:
        1. It has a higher last term, OR
        2. Same last term but longer (higher last index)

        Args:
            last_log_index: Candidate's last log index
            last_log_term: Candidate's last log term

        Returns:
            True if candidate's log is at least as up-to-date
        """
        my_last_term = self.last_term()
        my_last_index = self.last_index()

        if last_log_term > my_last_term:
            return True
        if last_log_term == my_last_term and last_log_index >= my_last_index:
            return True
        return False

    def __len__(self) -> int:
        """Number of entries (excluding sentinel)."""
        return len(self.entries) - 1

    def __repr__(self) -> str:
        entries_str = ", ".join(str(e) for e in self.entries[1:])
        return f"RaftLog([{entries_str}], commit={self.commit_index})"


# Example usage
if __name__ == "__main__":
    print("=== Raft Log Demonstration ===\n")

    log = RaftLog()
    print(f"Initial log: {log}")
    print(f"Last index: {log.last_index()}, Last term: {log.last_term()}")

    # Append entries as leader
    print("\nAppending entries as leader:")
    log.append(term=1, command="SET x = 1")
    log.append(term=1, command="SET y = 2")
    log.append(term=2, command="SET x = 3")
    print(f"Log: {log}")

    # Commit entries
    print("\nCommitting up to index 2:")
    committed = log.commit(2)
    print(f"Newly committed: {committed}")
    print(f"Log: {log}")

    # Demonstrate AppendEntries
    print("\n=== AppendEntries Demo ===")
    follower_log = RaftLog()
    follower_log.append(term=1, command="SET x = 1")
    print(f"Follower log: {follower_log}")

    # Leader sends entries
    leader_entries = [
        LogEntry(term=1, index=2, command="SET y = 2"),
        LogEntry(term=2, index=3, command="SET x = 3"),
    ]

    success, match = follower_log.append_entries(
        prev_log_index=1,
        prev_log_term=1,
        entries=leader_entries
    )
    print(f"AppendEntries result: success={success}, match_index={match}")
    print(f"Follower log after: {follower_log}")

    # Demonstrate log conflict resolution
    print("\n=== Log Conflict Demo ===")
    conflict_log = RaftLog()
    conflict_log.append(term=1, command="A")
    conflict_log.append(term=1, command="B")
    conflict_log.append(term=2, command="C_old")  # Will conflict
    print(f"Before: {conflict_log}")

    # Leader has different entry at index 3
    new_entries = [LogEntry(term=3, index=3, command="C_new")]
    success, match = conflict_log.append_entries(
        prev_log_index=2,
        prev_log_term=1,
        entries=new_entries
    )
    print(f"After conflict resolution: {conflict_log}")
    print("Entry at index 3 replaced (term 2 -> term 3)")
