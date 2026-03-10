"""Waitlist service backed by JSON storage."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from appointment_orchestrator.models.waitlist_entry import WaitlistEntry
from appointment_orchestrator.tools.geolocation_tool import calculate_distance, fetch_coordinates_from_area
from appointment_orchestrator.utils import ranking_utils


class WaitlistService:
    """Handles waitlist CRUD and ranking operations."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.data_file = data_file or (base_dir / "mock_data" / "waitlist.json")
        self.hospital_config_file = base_dir / "mock_data" / "hospital_config.json"

    def _read_waitlist(self) -> List[Dict]:
        if not self.data_file.exists():
            return []
        with self.data_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_waitlist(self, entries: List[Dict]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(entries, file, indent=2)

    def get_waitlist(self) -> List[Dict]:
        """Return waitlist entries."""
        return self._read_waitlist()

    def _get_hospital_coordinates(self) -> Optional[Dict[str, float]]:
        if not self.hospital_config_file.exists():
            return None
        with self.hospital_config_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        coords = payload.get("coordinates", {})
        if "lat" in coords and "lon" in coords:
            return {"lat": float(coords["lat"]), "lon": float(coords["lon"])}
        return None

    def validate_waitlist_entry(self, entry: Dict) -> Dict:
        """
        Validate waitlist entry data.

        Checks:
        - phone format (if phone is provided)
        - urgency value in [0, 1]
        - location format (if location is provided)
        Invalid entries are marked inactive.
        """
        updated = dict(entry)
        is_valid = True

        phone = updated.get("phone")
        if phone:
            phone_ok = re.fullmatch(r"^\+?[0-9]{10,15}$", str(phone).strip()) is not None
            if not phone_ok:
                is_valid = False

        urgency = updated.get("urgency")
        try:
            if urgency is None or int(urgency) not in (0, 1):
                is_valid = False
        except Exception:
            is_valid = False

        location = updated.get("location")
        if location:
            location_ok = re.fullmatch(r"^[A-Za-z0-9,\- ]{3,100}$", str(location).strip()) is not None
            if not location_ok:
                is_valid = False

        updated["status"] = updated.get("status", "waiting")
        if not is_valid:
            updated["status"] = "inactive"
        return updated

    def add_to_waitlist(self, patient: Dict) -> Dict:
        """Add a patient to waitlist if not already active."""
        entries = self._read_waitlist()
        patient_id = int(patient["patient_id"])
        for entry in entries:
            if int(entry.get("patient_id", -1)) == patient_id and entry.get("status") != "removed":
                return {"success": False, "message": "Patient already exists on waitlist."}

        waitlist_entry = WaitlistEntry(
            patient_id=patient_id,
            name=patient["name"],
            urgency=int(patient.get("urgency", 0)),
            distance_km=(
                float(patient["distance_km"])
                if patient.get("distance_km") is not None
                else None
            ),
            wait_hours=float(patient.get("wait_hours", 0)),
            phone=patient.get("phone"),
            location=patient.get("location"),
            latitude=patient.get("latitude"),
            longitude=patient.get("longitude"),
            status=patient.get("status", "waiting"),
        )
        entries.append(waitlist_entry.to_dict())
        self._write_waitlist(entries)
        return {"success": True, "message": "Patient added to waitlist.", "entry": waitlist_entry.to_dict()}

    def rank_waitlist(self) -> List[Dict]:
        """
        Return ranked waitlist entries with validation and optional geolocation distance.
        """
        entries = self._read_waitlist()
        hospital_coords = self._get_hospital_coordinates()
        enriched_entries = []

        for raw_entry in entries:
            validated = self.validate_waitlist_entry(raw_entry)
            if validated.get("status") == "inactive":
                enriched_entries.append(validated)
                continue

            lat = validated.get("latitude")
            lon = validated.get("longitude")
            patient_coords = None
            if lat is not None and lon is not None:
                patient_coords = {"lat": float(lat), "lon": float(lon)}
            elif validated.get("location"):
                fetched = fetch_coordinates_from_area(validated["location"])
                if fetched:
                    patient_coords = fetched
                    validated["latitude"] = fetched["lat"]
                    validated["longitude"] = fetched["lon"]

            if patient_coords and hospital_coords:
                validated["distance_km"] = round(
                    calculate_distance(patient_coords, hospital_coords) or 0.0, 2
                )
            elif validated.get("distance_km") is None:
                validated["distance_km"] = None

            enriched_entries.append(validated)

        # Persist validations and derived geolocation fields.
        self._write_waitlist(enriched_entries)

        active_entries = [entry for entry in enriched_entries if entry.get("status") != "inactive"]
        ranked_active = ranking_utils.rank_waitlist(active_entries)
        inactive_entries = [entry for entry in enriched_entries if entry.get("status") == "inactive"]
        return ranked_active + inactive_entries

    def update_waitlist_status(self, patient_id: int, status: str) -> Dict:
        """Update waitlist status for a patient."""
        entries = self._read_waitlist()
        for entry in entries:
            if int(entry.get("patient_id", -1)) == int(patient_id):
                entry["status"] = status
                self._write_waitlist(entries)
                return {"success": True, "message": "Waitlist status updated.", "entry": entry}
        return {"success": False, "message": "Patient not found in waitlist."}

    def remove_from_waitlist(self, patient_id: int) -> Dict:
        """Remove a patient from waitlist."""
        entries = self._read_waitlist()
        filtered = [entry for entry in entries if int(entry.get("patient_id", -1)) != int(patient_id)]
        if len(filtered) == len(entries):
            return {"success": False, "message": "Patient not found in waitlist."}
        self._write_waitlist(filtered)
        return {"success": True, "message": "Patient removed from waitlist."}
