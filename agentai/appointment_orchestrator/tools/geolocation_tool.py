"""Geolocation and coordinate utilities."""

import json
import os
import urllib.parse
import urllib.request
from typing import Dict, Optional

from appointment_orchestrator.utils.distance_utils import calculate_distance_km


def fetch_coordinates_from_area(area_name: str) -> Optional[Dict[str, float]]:
    """
    Resolve area name to coordinates using Google Geocoding API.

    Falls back to a deterministic mock value if API key/network is unavailable.
    """
    if not area_name:
        return None

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if api_key:
        query = urllib.parse.urlencode({"address": area_name, "key": api_key})
        url = f"https://maps.googleapis.com/maps/api/geocode/json?{query}"
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = payload.get("results", [])
            if results:
                location = results[0]["geometry"]["location"]
                return {"lat": float(location["lat"]), "lon": float(location["lng"])}
        except Exception:
            pass

    # Mock fallback to keep demo/testing stable without external API.
    mock_geocoding = {
        "Indiranagar Bangalore": {"lat": 12.9716, "lon": 77.5946},
        "Koramangala Bangalore": {"lat": 12.9352, "lon": 77.6245},
        "Whitefield Bangalore": {"lat": 12.9698, "lon": 77.7499},
    }
    return mock_geocoding.get(area_name)


def calculate_distance(patient_coords: Dict[str, float], hospital_coords: Dict[str, float]) -> Optional[float]:
    """Calculate distance in kilometers using Haversine method."""
    return calculate_distance_km(patient_coords, hospital_coords, method="haversine")

