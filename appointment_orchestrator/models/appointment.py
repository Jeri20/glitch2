"""Appointment data model."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Appointment:
    """Represents an appointment slot entry in the calendar."""

    slot_id: int
    doctor_id: int
    time: str
    status: str
    patient_id: Optional[int] = None
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return asdict(self)

