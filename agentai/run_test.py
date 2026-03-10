from appointment_orchestrator.orchestrator.appointment_orchestrator import (
    AppointmentOrchestrator,
    reset_system_state,
)

orchestrator = AppointmentOrchestrator()

print("=== RESET SYSTEM STATE ===")
print(reset_system_state())

print("=== TEST: BOOK APPOINTMENT ===")

result = orchestrator.handle_booking_request(
    patient_id=1,
    doctor_id=101,
    preferred_time="11:00"
)

print(result)

print("\n=== TEST: HANDLE CANCELLATION ===")

cancel_result = orchestrator.handle_cancellation_event(slot_id=6)
print(f"Status: {cancel_result.get('message')}")
if cancel_result.get("booked_patient_id"):
    print(f"Booked patient id: {cancel_result.get('booked_patient_id')}")
top_candidates = cancel_result.get("top_candidates", [])
if top_candidates:
    print("Top candidates offered:")
    for index, patient in enumerate(top_candidates, start=1):
        print(f"{index}. {patient.get('name')} (score: {patient.get('score')})")

print("\n=== TEST: WAITLIST RANKING ===")

waitlist = orchestrator.waitlist_service.rank_waitlist()
print("Ranked Waitlist:")
for index, patient in enumerate(waitlist, start=1):
    print(f"{index}. {patient.get('name')} (score: {patient.get('score')})")
