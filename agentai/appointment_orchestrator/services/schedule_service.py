"""Doctor schedule service backed by JSON storage."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.models.doctor_schedule import DoctorSchedule
from appointment_orchestrator.services.calendar_service import CalendarService


class ScheduleService:
    """Handles doctor schedule updates and slot lookups."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.data_file = data_file or (base_dir / "mock_data" / "doctor_schedule.json")
        self.calendar_service = CalendarService()

    def _read_schedule(self) -> List[Dict]:
        if not self.data_file.exists():
            return []
        with self.data_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_schedule(self, schedule_entries: List[Dict]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(schedule_entries, file, indent=2)

    def update_doctor_schedule(self, doctor_id: int, date: str, status: str) -> Dict:
        """Create or update doctor availability for a date."""
        schedule_entries = self._read_schedule()
        for entry in schedule_entries:
            if int(entry.get("doctor_id", -1)) == int(doctor_id) and entry.get("date") == date:
                entry["availability_status"] = status
                self._write_schedule(schedule_entries)
                return {"success": True, "message": "Schedule updated.", "schedule": entry}

        schedule = DoctorSchedule(
            doctor_id=int(doctor_id),
            date=date,
            availability_status=status,
        )
        schedule_entries.append(schedule.to_dict())
        self._write_schedule(schedule_entries)
        return {"success": True, "message": "Schedule created.", "schedule": schedule.to_dict()}

    def get_doctor_schedule(self, doctor_id: int, date: str) -> Optional[Dict]:
        """Fetch doctor schedule by doctor/date."""
        schedule_entries = self._read_schedule()
        for entry in schedule_entries:
            if int(entry.get("doctor_id", -1)) == int(doctor_id) and entry.get("date") == date:
                return entry
        return None

    def find_next_available_slots(
        self, doctor_id: int, count: int = 1, date: Optional[str] = None
    ) -> List[Dict]:
        """Return next N available slots for a doctor."""
        slots = self.calendar_service.get_available_slots(doctor_id=doctor_id, date=date)
        slots_sorted = sorted(slots, key=lambda s: (s.get("date", ""), s.get("time", "")))
        return slots_sorted[:count]

    def handle_doctor_delay(self, doctor_id: int, delay_minutes: int) -> Dict:
        """
        Shift upcoming booked appointments by delay minutes and return adjustment list.
        """
        print(f"Doctor {doctor_id} delayed by {delay_minutes} minutes")
        print("Shifting schedule...")

        appointments = self.calendar_service.get_appointments_by_doctor(doctor_id=doctor_id)
        appointments = sorted(appointments, key=lambda slot: (slot.get("date", ""), slot.get("time", "")))

        shifted = []
        for appointment in appointments:
            current_time = appointment.get("time")
            try:
                parsed = datetime.strptime(current_time, "%H:%M")
                new_time = (parsed + timedelta(minutes=delay_minutes)).strftime("%H:%M")
            except Exception:
                continue

            update_result = self.calendar_service.update_slot_time(
                slot_id=appointment["slot_id"],
                new_time=new_time,
            )
            if update_result.get("success"):
                patient_label = f"Patient-{appointment.get('patient_id')}"
                print(f"{patient_label} -> {new_time}")
                shifted.append(
                    {
                        "patient_id": appointment.get("patient_id"),
                        "slot_id": appointment.get("slot_id"),
                        "old_time": current_time,
                        "new_time": new_time,
                    }
                )

        return {
            "success": True,
            "message": "Doctor delay handled.",
            "doctor_id": doctor_id,
            "delay_minutes": delay_minutes,
            "shifted_appointments": shifted,
        }
