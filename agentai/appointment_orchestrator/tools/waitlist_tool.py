"""Agent tool wrapper for waitlist service."""

from typing import Dict, List

from appointment_orchestrator.services.waitlist_service import WaitlistService

waitlist_service = WaitlistService()


def get_waitlist() -> List[Dict]:
    """Tool: Fetch waitlist."""
    return waitlist_service.get_waitlist()


def rank_waitlist() -> List[Dict]:
    """Tool: Rank waitlist."""
    return waitlist_service.rank_waitlist()


def update_waitlist_status(patient_id: int, status: str) -> Dict:
    """Tool: Update waitlist status."""
    return waitlist_service.update_waitlist_status(patient_id=patient_id, status=status)

