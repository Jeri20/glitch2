"""Backward-compatible import wrapper for misspelled module name."""

from appointment_orchestrator.tools.calendar_tool import (
    book_appointment,
    cancel_appointment,
    check_doctor_availability,
    get_calendar_events,
)

__all__ = [
    "get_calendar_events",
    "check_doctor_availability",
    "book_appointment",
    "cancel_appointment",
]
