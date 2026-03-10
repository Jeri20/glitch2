"""Cancellation event detection utilities."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.services.calendar_service import CalendarService


class CancellationDetector:
    """Detects newly cancelled slots by comparing with a previous snapshot."""

    def __init__(self, snapshot_file: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.snapshot_file = snapshot_file or (base_dir / "mock_data" / "cancellation_snapshot.json")
        self.calendar_service = CalendarService()

    def _load_snapshot(self) -> Dict[int, str]:
        if not self.snapshot_file.exists():
            return {}
        with self.snapshot_file.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return {int(k): v for k, v in raw.items()}

    def _save_snapshot(self, snapshot: Dict[int, str]) -> None:
        self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        serialized = {str(k): v for k, v in snapshot.items()}
        with self.snapshot_file.open("w", encoding="utf-8") as file:
            json.dump(serialized, file, indent=2)

    def detect_cancellation_events(self) -> List[Dict]:
        """Return slots whose status changed to cancelled since last check."""
        events = self.calendar_service.get_calendar_events()
        current = {int(item["slot_id"]): item.get("status") for item in events}
        previous = self._load_snapshot()

        cancellations = []
        for slot in events:
            slot_id = int(slot["slot_id"])
            prev_status = previous.get(slot_id)
            if slot.get("status") == "cancelled" and prev_status != "cancelled":
                cancellations.append(slot)

        self._save_snapshot(current)
        return cancellations
