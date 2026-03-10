"""Doctor recommendation tool for alternate doctor suggestions."""

import json
from pathlib import Path
from typing import Dict, List, Optional


def _load_doctors(data_file: Optional[Path] = None) -> List[Dict]:
    base_dir = Path(__file__).resolve().parents[1]
    file_path = data_file or (base_dir / "mock_data" / "doctors.json")
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def recommend_doctors(specialty: str) -> List[Dict]:
    """Recommend available doctors matching specialty."""
    doctors = _load_doctors()
    return [
        doctor
        for doctor in doctors
        if doctor.get("specialty", "").lower() == specialty.lower()
        and doctor.get("availability_status", "available") == "available"
    ]

