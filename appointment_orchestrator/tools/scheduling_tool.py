"""Agent tool wrapper for scheduling operations."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from appointment_orchestrator.services.calendar_service import CalendarService
from appointment_orchestrator.services.schedule_service import ScheduleService

schedule_service = ScheduleService()
calendar_service = CalendarService()


def send_waitlist_offer(patients: List[Dict], slot: Dict, timeout_minutes: int = 5) -> Dict:
    """
    Simulate sending a slot offer and return the first patient who accepts.

    Response simulation is deterministic and follows candidate order:
    1st candidate -> NO
    2nd candidate -> YES
    3rd candidate -> NO
    Remaining candidates -> NO
    """
    if not patients:
        print("No waitlist patients to notify.")
        return {"accepted_patient": None, "responses": []}

    names = ", ".join([patient.get("name", "Unknown") for patient in patients])
    print(f"Sending slot offer to: {names}")

    response_sequence = ["NO", "YES", "NO"]
    offer_timestamp = datetime.utcnow()

    responses: List[Dict] = []
    accepted_patient = None
    for idx, patient in enumerate(patients):
        name = patient.get("name", "Unknown")
        response = response_sequence[idx] if idx < len(response_sequence) else "NO"
        # Simulate delayed responses in minutes (or default simulated order timing).
        simulated_delay = int(patient.get("simulated_response_delay_minutes", idx + 1))
        response_time = offer_timestamp + timedelta(minutes=simulated_delay)
        is_timed_out = response_time > (offer_timestamp + timedelta(minutes=timeout_minutes))
        if is_timed_out:
            response = "TIMEOUT"
        print(f"{name} -> {response}")
        responses.append(
            {
                "patient_id": patient.get("patient_id"),
                "name": name,
                "response": response,
                "offer_timestamp": offer_timestamp.isoformat(),
                "response_timestamp": response_time.isoformat(),
            }
        )
        if response == "YES" and accepted_patient is None:
            accepted_patient = patient
            break

    return {
        "accepted_patient": accepted_patient,
        "responses": responses,
        "slot_id": slot.get("slot_id"),
        "offer_timestamp": offer_timestamp.isoformat(),
        "timeout_minutes": timeout_minutes,
    }


def find_next_available_slots(
    doctor_id: int, count: int = 1, date: Optional[str] = None
) -> List[Dict]:
    """Tool: Find next available slots for a doctor."""
    return schedule_service.find_next_available_slots(doctor_id=doctor_id, count=count, date=date)


def reschedule_appointments(doctor_id: int, date: str) -> Dict:
    """
    Tool: Reschedule booked appointments for a doctor on a date to next available slots.
    """
    affected = calendar_service.get_appointments_by_doctor(doctor_id=doctor_id, date=date)
    replacement_slots = schedule_service.find_next_available_slots(doctor_id=doctor_id, count=len(affected))

    if len(replacement_slots) < len(affected):
        return {
            "success": False,
            "message": "Not enough available slots to reschedule all appointments.",
            "affected_appointments": affected,
            "replacement_slots": replacement_slots,
        }

    reassigned = []
    for old_slot, new_slot in zip(affected, replacement_slots):
        cancel_result = calendar_service.cancel_appointment(old_slot["slot_id"])
        if not cancel_result.get("success"):
            continue
        book_result = calendar_service.book_appointment(
            patient_id=old_slot.get("patient_id"),
            slot_id=new_slot.get("slot_id"),
        )
        reassigned.append(
            {
                "old_slot_id": old_slot.get("slot_id"),
                "new_slot_id": new_slot.get("slot_id"),
                "patient_id": old_slot.get("patient_id"),
                "booking_result": book_result.get("success"),
            }
        )

    return {
        "success": True,
        "message": "Appointments rescheduled.",
        "reassigned": reassigned,
    }
