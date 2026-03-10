"""Backward-compatible import wrapper for misspelled module name."""

from appointment_orchestrator.services.calendar_service import CalendarService

__all__ = ["CalendarService"]
