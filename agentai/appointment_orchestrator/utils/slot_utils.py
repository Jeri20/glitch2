"""Slot helper utilities."""

from typing import Dict, List, Optional


def filter_available_slots(calendar: List[Dict]) -> List[Dict]:
    """Filter available slots from a calendar list."""
    return [slot for slot in calendar if slot.get("status") == "available"]


def find_next_available_slot(calendar: List[Dict]) -> Optional[Dict]:
    """
    Find the earliest available slot by date/time where available.

    If date is missing, sort by slot_id as fallback.
    """
    available = filter_available_slots(calendar)
    if not available:
        return None
    return sorted(
        available,
        key=lambda s: (
            s.get("date", ""),
            s.get("time", ""),
            int(s.get("slot_id", 0)),
        ),
    )[0]

