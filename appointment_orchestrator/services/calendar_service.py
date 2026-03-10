"""Calendar service backed by JSON storage."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.utils.slot_utils import filter_available_slots


class CalendarService:
    """Handles appointment calendar retrieval and mutations."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.data_file = data_file or (base_dir / "mock_data" / "calendar.json")

    def _read_calendar(self) -> List[Dict]:
        if not self.data_file.exists():
            return []
        with self.data_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_calendar(self, calendar: List[Dict]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(calendar, file, indent=2)

    def get_calendar_events(self, date: Optional[str] = None) -> List[Dict]:
        """Return all events, optionally filtered by date."""
        calendar = self._read_calendar()
        if not date:
            return calendar
        return [event for event in calendar if event.get("date") == date]

    def check_doctor_availability(
        self, doctor_id: int, date_range: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Return available slots for a doctor, optionally restricted to specific dates.
        """
        events = self._read_calendar()
        filtered = [
            event
            for event in events
            if int(event.get("doctor_id", -1)) == int(doctor_id)
            and event.get("status") == "available"
            and (not date_range or event.get("date") in date_range)
        ]
        return sorted(filtered, key=lambda item: (item.get("date", ""), item.get("time", "")))

    def book_appointment(self, patient_id: int, slot_id: int) -> Dict:
        """Book an available slot for a patient."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                if slot.get("status") != "available":
                    return {"success": False, "message": "Slot is not available."}
                if bool(slot.get("locked", False)):
                    return {"success": False, "message": "Slot is already filled."}
                print(f"Booking appointment for patient {patient_id} in slot {slot.get('time')}")
                slot["status"] = "booked"
                slot["patient_id"] = patient_id
                slot["locked"] = False
                self._write_calendar(calendar)
                return {"success": True, "message": "Appointment booked.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def cancel_appointment(self, slot_id: int) -> Dict:
        """Cancel a booked slot."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                if slot.get("status") != "booked":
                    return {
                        "success": False,
                        "message": "Only booked slots can be cancelled.",
                        "slot": slot,
                    }
                slot["status"] = "cancelled"
                slot["previous_patient_id"] = slot.get("patient_id")
                slot["patient_id"] = None
                slot["locked"] = False
                self._write_calendar(calendar)
                return {"success": True, "message": "Appointment cancelled.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def release_cancelled_slot(self, slot_id: int) -> Dict:
        """Mark a cancelled slot as available so it can be reassigned."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                if slot.get("status") != "cancelled":
                    return {
                        "success": False,
                        "message": "Only cancelled slots can be released.",
                        "slot": slot,
                    }
                slot["status"] = "available"
                slot["patient_id"] = None
                slot["locked"] = False
                self._write_calendar(calendar)
                return {"success": True, "message": "Cancelled slot released.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def lock_slot(self, slot_id: int) -> Dict:
        """Lock a slot to prevent double booking during concurrent confirmations."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                if bool(slot.get("locked", False)):
                    return {"success": False, "message": "Slot already filled.", "slot": slot}
                if slot.get("status") not in ("available", "cancelled"):
                    return {"success": False, "message": "Slot is not open for locking.", "slot": slot}
                slot["locked"] = True
                self._write_calendar(calendar)
                return {"success": True, "message": "Slot locked.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def unlock_slot(self, slot_id: int) -> Dict:
        """Unlock a slot."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                slot["locked"] = False
                self._write_calendar(calendar)
                return {"success": True, "message": "Slot unlocked.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def update_slot_time(self, slot_id: int, new_time: str) -> Dict:
        """Update slot time for delay-adjustment workflows."""
        calendar = self._read_calendar()
        for slot in calendar:
            if int(slot.get("slot_id", -1)) == int(slot_id):
                slot["time"] = new_time
                self._write_calendar(calendar)
                return {"success": True, "message": "Slot time updated.", "slot": slot}
        return {"success": False, "message": "Slot not found.", "slot": None}

    def get_available_slots(self, doctor_id: int, date: Optional[str] = None) -> List[Dict]:
        """Get available slots for a doctor on an optional date."""
        events = self._read_calendar()
        doctor_events = [
            event
            for event in events
            if int(event.get("doctor_id", -1)) == int(doctor_id)
            and (not date or event.get("date") == date)
        ]
        return filter_available_slots(doctor_events)

    def get_appointments_by_doctor(
        self, doctor_id: int, date: Optional[str] = None
    ) -> List[Dict]:
        """Get booked appointments for a doctor on an optional date."""
        events = self._read_calendar()
        return [
            event
            for event in events
            if int(event.get("doctor_id", -1)) == int(doctor_id)
            and event.get("status") == "booked"
            and (not date or event.get("date") == date)
        ]
