"""Waitlist entry data model."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class WaitlistEntry:
    """Represents a patient on the waitlist."""

    patient_id: int
    name: str
    urgency: int
    distance_km: Optional[float]
    wait_hours: float
    phone: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str = "waiting"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return asdict(self)
