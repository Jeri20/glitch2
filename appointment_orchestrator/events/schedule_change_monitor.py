"""Doctor schedule change monitoring."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.services.calendar_service import CalendarService
from appointment_orchestrator.services.schedule_service import ScheduleService


class ScheduleChangeMonitor:
    """Detects changes in doctor schedule status compared to previous snapshot."""

    def __init__(
        self,
        schedule_file: Optional[Path] = None,
        snapshot_file: Optional[Path] = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.schedule_file = schedule_file or (base_dir / "mock_data" / "doctor_schedule.json")
        self.snapshot_file = snapshot_file or (base_dir / "mock_data" / "schedule_snapshot.json")
        self.calendar_service = CalendarService()
        self.schedule_service = ScheduleService(data_file=self.schedule_file)

    def _load_schedule(self) -> List[Dict]:
        if not self.schedule_file.exists():
            return []
        with self.schedule_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _load_snapshot(self) -> Dict[str, str]:
        if not self.snapshot_file.exists():
            return {}
        with self.snapshot_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_snapshot(self, snapshot: Dict[str, str]) -> None:
        self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        with self.snapshot_file.open("w", encoding="utf-8") as file:
            json.dump(snapshot, file, indent=2)

    def detect_schedule_changes(self) -> List[Dict]:
        """
        Detect modified schedule statuses.
        Key format: "{doctor_id}:{date}".
        """
        schedule_entries = self._load_schedule()
        current = {
            f"{entry['doctor_id']}:{entry['date']}": entry.get("availability_status", "unknown")
            for entry in schedule_entries
        }
        previous = self._load_snapshot()

        changes = []
        for entry in schedule_entries:
            key = f"{entry['doctor_id']}:{entry['date']}"
            if previous.get(key) != current[key]:
                changes.append(entry)

        self._save_snapshot(current)
        return changes

    def detect_schedule_change(self, doctor_id: int, date: str) -> Dict:
        """
        Detect and process a doctor unavailability event for a specific date.

        Steps:
        1) Retrieve affected booked appointments
        2) Cancel affected slots
        3) Find next available slots
        4) Reassign appointments
        """
        print(f"Doctor {doctor_id} unavailable on {date}")

        affected = self.calendar_service.get_appointments_by_doctor(doctor_id=doctor_id, date=date)
        print("\nAffected appointments:")
        if not affected:
            print("None")
            return {"success": True, "message": "No affected appointments.", "reassigned": []}

        for appointment in affected:
            print(f"Patient-{appointment.get('patient_id')}")

        print("\nReassigning appointments...")
        replacement_slots = self.schedule_service.find_next_available_slots(
            doctor_id=doctor_id,
            count=len(affected),
        )

        reassigned = []
        failed = []
        for appointment, new_slot in zip(affected, replacement_slots):
            cancel_result = self.calendar_service.cancel_appointment(slot_id=appointment["slot_id"])
            if not cancel_result.get("success"):
                failed.append({"appointment": appointment, "reason": "cancel_failed"})
                continue

            book_result = self.calendar_service.book_appointment(
                patient_id=appointment["patient_id"],
                slot_id=new_slot["slot_id"],
            )
            if not book_result.get("success"):
                failed.append({"appointment": appointment, "reason": "book_failed"})
                continue

            print(f"Patient-{appointment.get('patient_id')} -> {new_slot.get('time')}")
            reassigned.append(
                {
                    "patient_id": appointment["patient_id"],
                    "old_slot_id": appointment["slot_id"],
                    "new_slot_id": new_slot["slot_id"],
                    "new_time": new_slot.get("time"),
                }
            )

        if len(replacement_slots) < len(affected):
            for pending in affected[len(replacement_slots) :]:
                failed.append({"appointment": pending, "reason": "no_available_slot"})

        return {
            "success": len(failed) == 0,
            "message": "Schedule change processed.",
            "affected_appointments": affected,
            "reassigned": reassigned,
            "failed": failed,
        }
