"""Central workflow controller for appointment automation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.events.cancellation_utils import CancellationDetector
from appointment_orchestrator.events.no_show_monitor import NoShowMonitor
from appointment_orchestrator.services.calendar_service import CalendarService
from appointment_orchestrator.services.schedule_service import ScheduleService
from appointment_orchestrator.services.waitlist_service import WaitlistService
from appointment_orchestrator.tools.scheduling_tool import send_waitlist_offer
from appointment_orchestrator.utils.slot_utils import find_next_available_slot


ORIGINAL_CALENDAR_DATA = [
    {"slot_id": 1, "doctor_id": 101, "date": "2026-03-10", "time": "09:00", "status": "booked", "patient_id": 1001, "locked": False},
    {"slot_id": 2, "doctor_id": 101, "date": "2026-03-10", "time": "10:00", "status": "booked", "patient_id": 1002, "locked": False},
    {"slot_id": 3, "doctor_id": 101, "date": "2026-03-10", "time": "11:00", "status": "available", "patient_id": None, "locked": False},
    {"slot_id": 4, "doctor_id": 101, "date": "2026-03-10", "time": "12:00", "status": "available", "patient_id": None, "locked": False},
    {"slot_id": 5, "doctor_id": 101, "date": "2026-03-10", "time": "13:00", "status": "booked", "patient_id": 1003, "locked": False},
    {"slot_id": 6, "doctor_id": 101, "date": "2026-03-10", "time": "14:00", "status": "cancelled", "patient_id": None, "locked": False},
    {"slot_id": 7, "doctor_id": 101, "date": "2026-03-10", "time": "15:00", "status": "available", "patient_id": None, "locked": False},
    {"slot_id": 8, "doctor_id": 101, "date": "2026-03-10", "time": "16:00", "status": "booked", "patient_id": 1004, "locked": False},
    {"slot_id": 9, "doctor_id": 101, "date": "2026-03-10", "time": "17:00", "status": "available", "patient_id": None, "locked": False},
    {"slot_id": 10, "doctor_id": 101, "date": "2026-03-10", "time": "18:00", "status": "available", "patient_id": None, "locked": False},
]

ORIGINAL_WAITLIST_DATA = [
    {
        "patient_id": 1,
        "name": "Ravi",
        "phone": "+919900000001",
        "location": "Indiranagar Bangalore",
        "latitude": None,
        "longitude": None,
        "distance_km": None,
        "urgency": 1,
        "wait_hours": 3,
        "status": "waiting",
    },
    {
        "patient_id": 2,
        "name": "Anita",
        "phone": "+919900000002",
        "location": "Koramangala Bangalore",
        "latitude": None,
        "longitude": None,
        "distance_km": None,
        "urgency": 0,
        "wait_hours": 5,
        "status": "waiting",
    },
    {
        "patient_id": 3,
        "name": "Rahul",
        "phone": "+919900000003",
        "location": "Whitefield Bangalore",
        "latitude": None,
        "longitude": None,
        "distance_km": None,
        "urgency": 1,
        "wait_hours": 2,
        "status": "waiting",
    },
]


class AppointmentOrchestrator:
    """Coordinates booking, cancellation, schedule change, and no-show workflows."""

    def __init__(self) -> None:
        self.calendar_service = CalendarService()
        self.waitlist_service = WaitlistService()
        self.schedule_service = ScheduleService()
        self.cancellation_detector = CancellationDetector()
        self.no_show_monitor = NoShowMonitor()

    @staticmethod
    def _extract_preferred_date_time(preferred_time: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Parse preferred datetime into (date, HH:MM time) for slot lookup."""
        if not preferred_time:
            return None, None

        if isinstance(preferred_time, datetime):
            return preferred_time.date().isoformat(), preferred_time.strftime("%H:%M")

        text = str(preferred_time).strip().replace("Z", "")
        formats = (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%H:%M:%S",
            "%H:%M",
        )
        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                if "Y" in fmt:
                    return parsed.date().isoformat(), parsed.strftime("%H:%M")
                return None, parsed.strftime("%H:%M")
            except ValueError:
                continue

        try:
            parsed = datetime.fromisoformat(text)
            return parsed.date().isoformat(), parsed.strftime("%H:%M")
        except ValueError:
            return None, text

    @staticmethod
    def _filter_and_sort_open_slots(slots: List[Dict]) -> List[Dict]:
        """Return open slots sorted by date/time/slot_id."""
        open_slots = [
            slot
            for slot in slots
            if slot.get("status") == "available" and not bool(slot.get("locked", False))
        ]
        return sorted(
            open_slots,
            key=lambda s: (s.get("date", ""), s.get("time", ""), int(s.get("slot_id", 0))),
        )

    def handle_booking_request(
        self,
        patient: Optional[Dict] = None,
        doctor_id: Optional[int] = None,
        date: Optional[str] = None,
        preferred_slot_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        name: Optional[str] = None,
        urgency: int = 0,
        distance_km: float = 0,
        wait_hours: float = 0,
        preferred_time: Optional[str] = None,
        phone: Optional[str] = None,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict:
        """
        Workflow 1 - Book appointment:
        1) Check availability
        2) Book if slot found
        3) Add to waitlist if no slot found
        """
        if patient is None and patient_id is None:
            return {"success": False, "message": "Either patient dict or patient_id is required."}
        if doctor_id is None:
            return {"success": False, "message": "doctor_id is required."}

        patient_data = patient or {
            "patient_id": int(patient_id),
            "name": name or f"Patient-{patient_id}",
            "urgency": urgency,
            "distance_km": distance_km,
            "wait_hours": wait_hours,
            "phone": phone,
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
        }

        print("Checking doctor availability...")
        preferred_date, preferred_time_only = self._extract_preferred_date_time(preferred_time)
        lookup_date = date or preferred_date

        # Search preferred date first when provided.
        available_slots = self.calendar_service.get_available_slots(doctor_id=doctor_id, date=lookup_date)
        # If no slots on preferred date, broaden search to any date before waitlisting.
        if not available_slots and lookup_date:
            available_slots = self.calendar_service.get_available_slots(doctor_id=doctor_id, date=None)
        # If the requested doctor has no availability, fallback to any doctor's open slots.
        if not available_slots:
            available_slots = self._filter_and_sort_open_slots(
                self.calendar_service.get_calendar_events(date=lookup_date)
            )
        if not available_slots and lookup_date:
            available_slots = self._filter_and_sort_open_slots(
                self.calendar_service.get_calendar_events(date=None)
            )
        if available_slots:
            # Keep routing to a valid doctor in case input doctor_id has no slots.
            doctor_id = int(available_slots[0].get("doctor_id", doctor_id))

        if preferred_time and not preferred_slot_id:
            time_match = next(
                (slot for slot in available_slots if slot.get("time") == preferred_time_only),
                None,
            )
            if time_match:
                preferred_slot_id = int(time_match["slot_id"])

        if preferred_slot_id:
            target = next(
                (slot for slot in available_slots if int(slot.get("slot_id", -1)) == int(preferred_slot_id)),
                None,
            )
            # If requested slot is unavailable, fallback to the next available one.
            if not target:
                target = find_next_available_slot(available_slots)
        else:
            target = find_next_available_slot(available_slots)

        if target:
            # Defensive validation before booking to keep booking rules explicit at orchestration layer.
            events = self.calendar_service.get_calendar_events()
            selected_slot = next(
                (slot for slot in events if int(slot.get("slot_id", -1)) == int(target["slot_id"])),
                None,
            )
            if not selected_slot or selected_slot.get("status") != "available":
                return {"success": False, "message": "Slot is not available."}
            print("Booking appointment...")
            print(
                f"Booking appointment for patient {patient_data['patient_id']} at {target.get('time')}"
            )
            return self.calendar_service.book_appointment(
                patient_id=int(patient_data["patient_id"]),
                slot_id=int(target["slot_id"]),
            )

        waitlist_result = self.waitlist_service.add_to_waitlist(patient=patient_data)
        return {
            "success": False,
            "message": "No slots available. Patient moved to waitlist.",
            "waitlist_result": waitlist_result,
        }

    def handle_cancellation_event(self, slot_id: int) -> Dict:
        """
        Workflow 2 - Cancellation handling:
        1) Detect/mark cancellation
        2) Rank waitlist
        3) Select top 3
        4) Offer slot (simulated)
        5) First patient gets slot
        """
        print(f"Cancellation detected for slot {slot_id}")

        events = self.calendar_service.get_calendar_events()
        slot = next((item for item in events if int(item.get("slot_id", -1)) == int(slot_id)), None)
        if slot is None:
            return {"success": False, "message": "Slot not found."}

        # If already cancelled, proceed directly with waitlist refill flow.
        if slot.get("status") == "cancelled":
            cancellation = {"success": True, "message": "Slot already cancelled.", "slot": slot}
        else:
            cancellation = self.calendar_service.cancel_appointment(slot_id=slot_id)
            if not cancellation.get("success"):
                return cancellation

        ranked = self.waitlist_service.rank_waitlist()
        print("\nRanking waitlist...")
        print("\nTop candidates:")
        for index, patient in enumerate(ranked[:3], start=1):
            print(f"{index}. {patient.get('name', 'Unknown')} ({patient.get('score', 0)})")

        top_candidates = ranked[:3]
        print("\nSending slot offers...")
        if not top_candidates:
            return {
                "success": True,
                "message": "Slot cancelled. No waitlist candidates available.",
                "slot": cancellation.get("slot"),
                "ranked_waitlist": ranked,
                "top_candidates": [],
            }

        offer_result = send_waitlist_offer(top_candidates, slot, timeout_minutes=5)
        winner = offer_result.get("accepted_patient")
        if not winner:
            return {
                "success": True,
                "message": "No patient accepted the slot offer.",
                "offered_to": [candidate["patient_id"] for candidate in top_candidates],
                "responses": offer_result.get("responses", []),
                "slot": cancellation.get("slot"),
                "ranked_waitlist": ranked,
                "top_candidates": top_candidates,
            }

        print(f"\n{winner.get('name', 'Unknown')} replied YES")
        print(f"\nBooking slot for {winner.get('name', 'Unknown')}")

        lock_result = self.calendar_service.lock_slot(slot_id=slot_id)
        if not lock_result.get("success"):
            return {
                "success": False,
                "message": "Slot already filled.",
                "lock_result": lock_result,
                "ranked_waitlist": ranked,
                "top_candidates": top_candidates,
                "responses": offer_result.get("responses", []),
            }

        release_result = self.calendar_service.release_cancelled_slot(slot_id=slot_id)
        if not release_result.get("success"):
            self.calendar_service.unlock_slot(slot_id=slot_id)
            return {
                "success": False,
                "message": "Could not prepare cancelled slot for reassignment.",
                "release_result": release_result,
                "ranked_waitlist": ranked,
                "top_candidates": top_candidates,
            }

        booking = self.calendar_service.book_appointment(
            patient_id=int(winner["patient_id"]),
            slot_id=slot_id,
        )
        if booking.get("success"):
            self.waitlist_service.update_waitlist_status(
                patient_id=int(winner["patient_id"]),
                status="booked",
            )
            return {
                "success": True,
                "message": "Cancelled slot reassigned from waitlist.",
                "offered_to": [candidate["patient_id"] for candidate in top_candidates],
                "booked_patient_id": winner["patient_id"],
                "slot": booking.get("slot"),
                "responses": offer_result.get("responses", []),
                "ranked_waitlist": ranked,
                "top_candidates": top_candidates,
            }

        return {
            "success": False,
            "message": "Failed to reassign cancelled slot.",
            "offered_to": [candidate["patient_id"] for candidate in top_candidates],
            "booking_result": booking,
            "responses": offer_result.get("responses", []),
            "ranked_waitlist": ranked,
            "top_candidates": top_candidates,
        }

    def handle_doctor_delay(self, doctor_id: int, delay_minutes: int) -> Dict:
        """Handle doctor delay by shifting upcoming appointments."""
        return self.schedule_service.handle_doctor_delay(
            doctor_id=doctor_id,
            delay_minutes=delay_minutes,
        )

    def handle_no_show_with_grace_period(
        self,
        slot_id: int,
        grace_period_minutes: int = 10,
    ) -> Dict:
        """Apply patient grace period and trigger waitlist replacement when expired."""
        return self.no_show_monitor.enforce_grace_period(
            slot_id=slot_id,
            orchestrator=self,
            grace_period_minutes=grace_period_minutes,
        )

    def handle_schedule_change(self, doctor_id: int, date: str, new_status: str) -> Dict:
        """
        Workflow 3 - Doctor schedule change:
        1) Update schedule status
        2) Retrieve affected appointments
        3) Find next available slots
        4) Reassign appointments
        """
        schedule_update = self.schedule_service.update_doctor_schedule(
            doctor_id=doctor_id,
            date=date,
            status=new_status,
        )
        if new_status != "unavailable":
            return {
                "success": True,
                "message": "Schedule updated; no reassignment required.",
                "schedule": schedule_update.get("schedule"),
            }

        affected = self.calendar_service.get_appointments_by_doctor(doctor_id=doctor_id, date=date)
        fallback_slots = self.schedule_service.find_next_available_slots(
            doctor_id=doctor_id,
            count=len(affected),
        )

        reassigned = []
        failed = []
        for appointment, new_slot in zip(affected, fallback_slots):
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

            reassigned.append(
                {
                    "patient_id": appointment["patient_id"],
                    "old_slot_id": appointment["slot_id"],
                    "new_slot_id": new_slot["slot_id"],
                }
            )

        # Any appointments that could not be mapped to available slots are reported.
        if len(fallback_slots) < len(affected):
            for missing in affected[len(fallback_slots) :]:
                failed.append({"appointment": missing, "reason": "no_available_slot"})

        return {
            "success": len(failed) == 0,
            "message": "Schedule change processed.",
            "reassigned": reassigned,
            "failed": failed,
        }

    def handle_no_show_event(self, slot_id: int, standby_patient: Dict) -> Dict:
        """
        Workflow 4 - No-show handling:
        1) Detect risk (external models can set no_show_probability)
        2) Notify/prepare standby patient
        3) Assign standby if no-show confirmed
        """
        return self.no_show_monitor.assign_standby_patient(
            slot_id=slot_id,
            standby_patient_id=int(standby_patient["patient_id"]),
        )

    def poll_cancellations(self) -> List[Dict]:
        """Optional helper to poll newly detected cancellation events."""
        return self.cancellation_detector.detect_cancellation_events()


def simulate_cancellation_flow(slot_id: int = 6) -> Dict:
    """
    Demonstration helper for autonomous cancellation workflow.

    Steps:
    1) Cancel appointment slot
    2) Trigger cancellation orchestration
    3) Print ranked waitlist
    4) Print top 3 candidates
    """
    orchestrator = AppointmentOrchestrator()

    print(f"\n=== SIMULATION: CANCEL SLOT {slot_id} ===")
    cancel_result = orchestrator.calendar_service.cancel_appointment(slot_id=slot_id)
    print("Cancel result:", cancel_result)

    print("\n=== SIMULATION: HANDLE CANCELLATION ===")
    workflow_result = orchestrator.handle_cancellation_event(slot_id=slot_id)

    ranked_waitlist = workflow_result.get("ranked_waitlist", orchestrator.waitlist_service.rank_waitlist())
    top_candidates = workflow_result.get("top_candidates", ranked_waitlist[:3])

    print("\nRanked waitlist:")
    for patient in ranked_waitlist:
        print(f"- {patient.get('name', 'Unknown')} (score: {patient.get('score', 0)})")

    print("\nSelected top 3 candidates:")
    for patient in top_candidates:
        print(f"- {patient.get('name', 'Unknown')} (score: {patient.get('score', 0)})")

    return {
        "cancel_result": cancel_result,
        "workflow_result": workflow_result,
        "ranked_waitlist": ranked_waitlist,
        "top_candidates": top_candidates,
    }


def reset_system_state() -> Dict:
    """Reset calendar and waitlist JSON files to original mock data."""
    base_dir = Path(__file__).resolve().parents[1]
    calendar_file = base_dir / "mock_data" / "calendar.json"
    waitlist_file = base_dir / "mock_data" / "waitlist.json"

    with calendar_file.open("w", encoding="utf-8") as file:
        json.dump(ORIGINAL_CALENDAR_DATA, file, indent=2)
    with waitlist_file.open("w", encoding="utf-8") as file:
        json.dump(ORIGINAL_WAITLIST_DATA, file, indent=2)

    return {"success": True, "message": "System state reset.", "files": [str(calendar_file), str(waitlist_file)]}
