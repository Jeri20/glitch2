"""Agent tool wrapper for calendar service."""

from typing import Dict, List, Optional

from appointment_orchestrator.services.calendar_service import CalendarService

calendar_service = CalendarService()


def get_calendar_events(date: Optional[str] = None) -> List[Dict]:
    """Tool: Fetch calendar events."""
    return calendar_service.get_calendar_events(date=date)


def check_doctor_availability(doctor_id: int, date_range: Optional[List[str]] = None) -> List[Dict]:
    """Tool: Check available slots for a doctor."""
    return calendar_service.check_doctor_availability(doctor_id=doctor_id, date_range=date_range)


def book_appointment(patient_id: int, slot_id: int) -> Dict:
    """Tool: Book appointment slot."""
    return calendar_service.book_appointment(patient_id=patient_id, slot_id=slot_id)


def cancel_appointment(slot_id: int) -> Dict:
    """Tool: Cancel booked appointment."""
    return calendar_service.cancel_appointment(slot_id=slot_id)

