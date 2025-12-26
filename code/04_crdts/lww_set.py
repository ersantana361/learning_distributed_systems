"""
LWW-Element-Set (Last-Writer-Wins Set) CRDT Implementation

A LWW-Set allows adding and removing elements with timestamps.
Each element has an add timestamp and a remove timestamp.
The element is in the set if add_ts > remove_ts.

Key properties:
- Supports add and remove operations
- Concurrent add/remove resolved by comparing timestamps
- Configurable bias for equal timestamps

Variants:
- Add-bias: Element is in set if add_ts >= remove_ts
- Remove-bias: Element is in set if add_ts > remove_ts

Related lectures: 7.3 Eventual Consistency, 8.1 Collaboration Software
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Set, Tuple
from enum import Enum


class Bias(Enum):
    """Bias for resolving ties when add and remove have same timestamp."""
    ADD = "add"       # Prefer add on tie
    REMOVE = "remove" # Prefer remove on tie


@dataclass
class LWWSet:
    """
    A Last-Writer-Wins Element Set.

    Maintains two maps:
    - add_map: element -> timestamp of last add
    - remove_map: element -> timestamp of last remove

    An element is in the set if its add timestamp is greater than
    its remove timestamp (or equal, depending on bias).
    """

    node_id: str
    add_map: Dict[Any, float] = field(default_factory=dict)
    remove_map: Dict[Any, float] = field(default_factory=dict)
    bias: Bias = Bias.ADD  # What to do on timestamp tie

    def add(self, element: Any, timestamp: float) -> bool:
        """
        Add an element to the set.

        Args:
            element: The element to add
            timestamp: The timestamp of this operation

        Returns:
            True if the add timestamp was updated
        """
        current_ts = self.add_map.get(element, float('-inf'))
        if timestamp > current_ts:
            self.add_map[element] = timestamp
            return True
        return False

    def remove(self, element: Any, timestamp: float) -> bool:
        """
        Remove an element from the set.

        Args:
            element: The element to remove
            timestamp: The timestamp of this operation

        Returns:
            True if the remove timestamp was updated
        """
        current_ts = self.remove_map.get(element, float('-inf'))
        if timestamp > current_ts:
            self.remove_map[element] = timestamp
            return True
        return False

    def contains(self, element: Any) -> bool:
        """
        Check if an element is in the set.

        An element is present if:
        - It has been added (exists in add_map)
        - AND its add timestamp beats its remove timestamp

        Args:
            element: The element to check

        Returns:
            True if the element is currently in the set
        """
        if element not in self.add_map:
            return False

        add_ts = self.add_map[element]
        remove_ts = self.remove_map.get(element, float('-inf'))

        if add_ts > remove_ts:
            return True
        elif add_ts == remove_ts:
            # Use bias to break tie
            return self.bias == Bias.ADD
        return False

    def value(self) -> Set[Any]:
        """
        Get the current set of elements.

        Returns:
            Set of all elements currently in the set
        """
        return {elem for elem in self.add_map if self.contains(elem)}

    def merge(self, other: LWWSet) -> LWWSet:
        """
        Merge with another LWW-Set.

        Takes the maximum timestamp for each element in both maps.

        Args:
            other: Another LWW-Set to merge with

        Returns:
            A new merged LWW-Set
        """
        merged_add = {}
        merged_remove = {}

        # Merge add maps
        all_elements = set(self.add_map.keys()) | set(other.add_map.keys())
        for elem in all_elements:
            merged_add[elem] = max(
                self.add_map.get(elem, float('-inf')),
                other.add_map.get(elem, float('-inf'))
            )

        # Merge remove maps
        all_removed = set(self.remove_map.keys()) | set(other.remove_map.keys())
        for elem in all_removed:
            merged_remove[elem] = max(
                self.remove_map.get(elem, float('-inf')),
                other.remove_map.get(elem, float('-inf'))
            )

        return LWWSet(self.node_id, merged_add, merged_remove, self.bias)

    def merge_in_place(self, other: LWWSet) -> None:
        """
        Merge another LWW-Set into this one (mutating).

        Args:
            other: Another LWW-Set to merge with
        """
        # Merge add maps
        for elem, ts in other.add_map.items():
            if ts > self.add_map.get(elem, float('-inf')):
                self.add_map[elem] = ts

        # Merge remove maps
        for elem, ts in other.remove_map.items():
            if ts > self.remove_map.get(elem, float('-inf')):
                self.remove_map[elem] = ts

    def get_state(self) -> Tuple[Dict[Any, float], Dict[Any, float]]:
        """Get the internal state for serialization."""
        return (self.add_map.copy(), self.remove_map.copy())

    @classmethod
    def from_state(
        cls,
        node_id: str,
        add_map: Dict[Any, float],
        remove_map: Dict[Any, float],
        bias: Bias = Bias.ADD
    ) -> LWWSet:
        """Create an LWW-Set from serialized state."""
        return cls(node_id, add_map.copy(), remove_map.copy(), bias)

    def __repr__(self) -> str:
        return f"LWWSet(elements={self.value()}, bias={self.bias.value})"


# Example usage and demonstration
if __name__ == "__main__":
    print("=== LWW-Set Demonstration ===\n")

    # Simulate a shopping cart that syncs across devices
    cart_phone = LWWSet("phone")
    cart_laptop = LWWSet("laptop")

    print("Scenario: Shopping cart syncing across devices\n")

    # Add items on phone
    cart_phone.add("apple", timestamp=1.0)
    cart_phone.add("banana", timestamp=2.0)
    cart_phone.add("orange", timestamp=3.0)
    print(f"1. Phone adds items:")
    print(f"   Cart: {cart_phone.value()}")

    # Sync to laptop
    cart_laptop.merge_in_place(cart_phone)
    print(f"\n2. Laptop syncs:")
    print(f"   Cart: {cart_laptop.value()}")

    # Concurrent operations: phone removes banana, laptop adds milk
    cart_phone.remove("banana", timestamp=4.0)
    cart_laptop.add("milk", timestamp=4.5)
    print(f"\n3. Concurrent updates (offline):")
    print(f"   Phone removes banana (t=4.0)")
    print(f"   Laptop adds milk (t=4.5)")
    print(f"   Phone cart: {cart_phone.value()}")
    print(f"   Laptop cart: {cart_laptop.value()}")

    # Merge
    cart_phone.merge_in_place(cart_laptop)
    cart_laptop.merge_in_place(cart_phone)
    print(f"\n4. After sync:")
    print(f"   Phone cart: {cart_phone.value()}")
    print(f"   Laptop cart: {cart_laptop.value()}")
    print("   Both carts converge!")

    # Demonstrate add-wins vs remove-wins on tie
    print("\n=== Bias Demonstration ===")

    set_add_bias = LWWSet("a", bias=Bias.ADD)
    set_remove_bias = LWWSet("b", bias=Bias.REMOVE)

    # Same timestamp for add and remove
    set_add_bias.add("item", timestamp=5.0)
    set_add_bias.remove("item", timestamp=5.0)

    set_remove_bias.add("item", timestamp=5.0)
    set_remove_bias.remove("item", timestamp=5.0)

    print(f"Add and remove at same timestamp (5.0):")
    print(f"  Add-bias set contains 'item': {set_add_bias.contains('item')}")
    print(f"  Remove-bias set contains 'item': {set_remove_bias.contains('item')}")

    # Demonstrate re-add after remove
    print("\n=== Re-add After Remove ===")
    cart = LWWSet("demo")
    cart.add("item", timestamp=1.0)
    print(f"After add at t=1.0: {cart.value()}")

    cart.remove("item", timestamp=2.0)
    print(f"After remove at t=2.0: {cart.value()}")

    cart.add("item", timestamp=3.0)
    print(f"After re-add at t=3.0: {cart.value()}")
    print("Re-adding works because add_ts (3.0) > remove_ts (2.0)")
