"""Demo script for Intelligent Appointment Booking Agent workflows."""

import json
from pathlib import Path

from appointment_orchestrator.events.no_show_monitor import NoShowMonitor
from appointment_orchestrator.events.schedule_change_monitor import ScheduleChangeMonitor
from appointment_orchestrator.orchestrator.appointment_orchestrator import AppointmentOrchestrator


def _mark_slot_unchecked(slot_id: int) -> None:
    """Mark a booked slot as not checked-in for no-show simulation."""
    data_file = Path(__file__).resolve().parent / "appointment_orchestrator" / "mock_data" / "calendar.json"
    if not data_file.exists():
        return
    with data_file.open("r", encoding="utf-8") as file:
        calendar = json.load(file)

    for slot in calendar:
        if int(slot.get("slot_id", -1)) == int(slot_id):
            slot["checked_in"] = False
            break

    with data_file.open("w", encoding="utf-8") as file:
        json.dump(calendar, file, indent=2)


def main() -> None:
    """Run end-to-end demo simulation."""
    orchestrator = AppointmentOrchestrator()
    schedule_monitor = ScheduleChangeMonitor()
    no_show_monitor = NoShowMonitor()

    print("=== DEMO START ===\n")

    print("Booking appointment...\n")
    booking = orchestrator.handle_booking_request(
        patient_id=9001,
        name="Demo Patient",
        doctor_id=101,
        preferred_time="11:00",
    )
    if booking.get("success"):
        print(f"Appointment booked at {booking.get('slot', {}).get('time')}\n")
    else:
        print(f"Booking failed: {booking.get('message')}\n")

    print("Simulating cancellation...\n")
    cancellation_result = orchestrator.handle_cancellation_event(slot_id=6)
    print(f"Cancellation flow status: {cancellation_result.get('message')}\n")

    print("Simulating waitlist ranking...\n")
    ranked_waitlist = orchestrator.waitlist_service.rank_waitlist()
    for patient in ranked_waitlist:
        print(f"- {patient.get('name')} (score: {patient.get('score')})")
    print()

    print("Simulating doctor schedule change...\n")
    date = "2026-03-10"
    schedule_result = schedule_monitor.detect_schedule_change(doctor_id=101, date=date)
    print(f"Schedule change status: {schedule_result.get('message')}\n")

    print("Simulating no-show...\n")
    events = orchestrator.calendar_service.get_calendar_events()
    booked_slot = next((slot for slot in events if slot.get("status") == "booked"), None)
    if booked_slot:
        _mark_slot_unchecked(booked_slot["slot_id"])
        no_show_result = no_show_monitor.detect_no_show(
            slot_id=booked_slot["slot_id"],
            orchestrator=orchestrator,
        )
        print(f"No-show status: {no_show_result.get('message')}\n")
    else:
        print("No booked slot available for no-show simulation.\n")

    print("=== DEMO END ===")


if __name__ == "__main__":
    main()

