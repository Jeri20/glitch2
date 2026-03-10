"""No-show risk and fallback assignment utilities."""

from typing import Any, Dict, List

from appointment_orchestrator.services.calendar_service import CalendarService


class NoShowMonitor:
    """Provides helpers for no-show risk detection and standby assignment."""

    def __init__(self) -> None:
        self.calendar_service = CalendarService()

    def is_high_risk(self, appointment: Dict, threshold: float = 0.7) -> bool:
        """Return True if no-show probability exceeds threshold."""
        probability = float(appointment.get("no_show_probability", 0))
        return probability >= threshold

    def detect_high_risk_patients(
        self, appointments: List[Dict], threshold: float = 0.7
    ) -> List[Dict]:
        """Filter high-risk appointments."""
        return [appt for appt in appointments if self.is_high_risk(appt, threshold=threshold)]

    def assign_standby_patient(self, slot_id: int, standby_patient_id: int) -> Dict:
        """
        Assign standby patient when original patient is absent.

        The booked slot is cancelled first, then booked for standby patient.
        """
        cancel_result = self.calendar_service.cancel_appointment(slot_id=slot_id)
        if not cancel_result.get("success"):
            return {
                "success": False,
                "message": "Could not cancel original appointment for no-show handling.",
                "details": cancel_result,
            }

        booking_result = self.calendar_service.book_appointment(
            patient_id=standby_patient_id,
            slot_id=slot_id,
        )
        if booking_result.get("success"):
            return {
                "success": True,
                "message": "Standby patient assigned to slot.",
                "slot": booking_result.get("slot"),
            }
        return {
            "success": False,
            "message": "Standby assignment failed after cancellation.",
            "details": booking_result,
        }

    def detect_no_show(self, slot_id: int, orchestrator: Any) -> Dict:
        """
        Detect no-show for a slot and trigger waitlist replacement workflow.

        check-in is simulated with a boolean field `checked_in` in calendar slot.
        Missing or False is treated as no-show.
        """
        events = self.calendar_service.get_calendar_events()
        slot = next((item for item in events if int(item.get("slot_id", -1)) == int(slot_id)), None)
        if not slot:
            return {"success": False, "message": "Slot not found."}

        checked_in = bool(slot.get("checked_in", False))
        if checked_in:
            return {
                "success": True,
                "message": "Patient checked in. No no-show action required.",
                "slot": slot,
            }

        patient_label = slot.get("patient_name") or f"Patient-{slot.get('patient_id')}"
        print(f"Patient {patient_label} did not check in.")
        print("\nTriggering waitlist replacement...")

        workflow_result = orchestrator.handle_cancellation_event(slot_id=slot_id)
        return {
            "success": True,
            "message": "No-show processed and replacement workflow triggered.",
            "slot": slot,
            "replacement_result": workflow_result,
        }

    def enforce_grace_period(
        self,
        slot_id: int,
        orchestrator: Any,
        grace_period_minutes: int = 10,
    ) -> Dict:
        """
        Enforce patient grace period. If not checked in, release slot and trigger waitlist.
        """
        events = self.calendar_service.get_calendar_events()
        slot = next((item for item in events if int(item.get("slot_id", -1)) == int(slot_id)), None)
        if not slot:
            return {"success": False, "message": "Slot not found."}

        checked_in = bool(slot.get("checked_in", False))
        if checked_in:
            return {"success": True, "message": "Patient checked in within grace period.", "slot": slot}

        print(
            f"Grace period of {grace_period_minutes} minutes expired for slot {slot_id}. "
            "Releasing slot..."
        )
        workflow_result = orchestrator.handle_cancellation_event(slot_id=slot_id)
        return {
            "success": True,
            "message": "Grace period expired. Waitlist replacement triggered.",
            "slot": slot,
            "replacement_result": workflow_result,
        }
