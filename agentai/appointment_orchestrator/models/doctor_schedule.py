"""Doctor schedule data model."""

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class DoctorSchedule:
    """Represents a doctor's availability status for a date."""

    doctor_id: int
    date: str
    availability_status: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return asdict(self)

