"""
Lamport Clock Implementation

Based on Leslie Lamport's 1978 paper "Time, Clocks, and the Ordering of Events
in a Distributed System".

Key properties:
- If event A happens-before event B, then L(A) < L(B)
- The converse is NOT true: L(A) < L(B) does NOT imply A happens-before B
- Provides total ordering when combined with node ID as tiebreaker

Related lecture: 4.1 Logical Time
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class LamportClock:
    """
    A Lamport logical clock for a single node.

    The clock maintains a monotonically increasing counter that:
    - Increments on every local event
    - Synchronizes with received timestamps to maintain causality
    """

    node_id: str
    time: int = 0

    def tick(self) -> int:
        """
        Record a local event. Increments the clock.

        Returns:
            The new timestamp after the event
        """
        self.time += 1
        return self.time

    def send(self) -> Tuple[int, str]:
        """
        Prepare to send a message. Increments clock and returns timestamp.

        The send event itself is a local event that advances the clock.

        Returns:
            Tuple of (timestamp, node_id) to attach to the message
        """
        self.time += 1
        return (self.time, self.node_id)

    def receive(self, msg_timestamp: int) -> int:
        """
        Receive a message with a timestamp.

        Updates local clock to be greater than both current time and
        the received timestamp, ensuring causal ordering.

        Args:
            msg_timestamp: The Lamport timestamp from the received message

        Returns:
            The new local timestamp after receiving
        """
        # Take max of local time and received time, then increment
        # This ensures the receive event has a timestamp greater than
        # both the send event and any prior local events
        self.time = max(self.time, msg_timestamp) + 1
        return self.time

    def timestamp(self) -> Tuple[int, str]:
        """
        Get current timestamp with node ID for total ordering.

        Using (time, node_id) pairs allows breaking ties between
        events with the same Lamport time. The node_id ordering
        is arbitrary but consistent.

        Returns:
            Tuple of (time, node_id)
        """
        return (self.time, self.node_id)


def compare_timestamps(ts1: Tuple[int, str], ts2: Tuple[int, str]) -> int:
    """
    Compare two Lamport timestamps for total ordering.

    Args:
        ts1: First timestamp (time, node_id)
        ts2: Second timestamp (time, node_id)

    Returns:
        -1 if ts1 < ts2, 0 if equal, 1 if ts1 > ts2
    """
    time1, node1 = ts1
    time2, node2 = ts2

    if time1 < time2:
        return -1
    elif time1 > time2:
        return 1
    else:
        # Times equal, use node_id as tiebreaker
        if node1 < node2:
            return -1
        elif node1 > node2:
            return 1
        else:
            return 0


# Example usage and demonstration
if __name__ == "__main__":
    print("=== Lamport Clock Demonstration ===\n")

    # Create three processes
    alice = LamportClock("alice")
    bob = LamportClock("bob")
    carol = LamportClock("carol")

    print("Initial state: all clocks at 0")
    print(f"  Alice: {alice.time}, Bob: {bob.time}, Carol: {carol.time}\n")

    # Scenario: Alice sends to Bob, Bob sends to Carol
    print("1. Alice does local work")
    alice.tick()
    print(f"   Alice clock: {alice.time}")

    print("\n2. Alice sends message to Bob")
    msg1_ts, msg1_sender = alice.send()
    print(f"   Message timestamp: {msg1_ts} from {msg1_sender}")

    print("\n3. Bob receives message from Alice")
    bob.receive(msg1_ts)
    print(f"   Bob clock after receive: {bob.time}")

    print("\n4. Bob does local work")
    bob.tick()
    print(f"   Bob clock: {bob.time}")

    print("\n5. Bob sends message to Carol")
    msg2_ts, msg2_sender = bob.send()
    print(f"   Message timestamp: {msg2_ts} from {msg2_sender}")

    print("\n6. Carol receives message from Bob")
    carol.receive(msg2_ts)
    print(f"   Carol clock after receive: {carol.time}")

    # Demonstrate concurrent events
    print("\n=== Concurrent Events ===")
    print("Meanwhile, Alice does more local work without communicating...")
    alice.tick()
    alice.tick()
    print(f"Alice clock: {alice.time}, Carol clock: {carol.time}")
    print("These events are concurrent - neither happened-before the other")
    print("But Lamport clocks can't distinguish this from causal ordering!")

    # Demonstrate total ordering with tiebreaker
    print("\n=== Total Ordering with Node ID Tiebreaker ===")
    events = [
        (2, "alice"),
        (2, "bob"),
        (3, "carol"),
        (1, "alice"),
    ]
    print("Unsorted events:", events)
    sorted_events = sorted(events, key=lambda x: (x[0], x[1]))
    print("Sorted events:  ", sorted_events)
