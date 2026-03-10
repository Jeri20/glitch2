"""Hospital allocation agent using session memory and geo-distance."""

from geopy.distance import geodesic
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


class HospitalAllocationAgent:
    """Allocates a hospital using memory, preferences, and nearest distance."""

    DEFAULT_HOSPITALS = [
        {"name": "Apollo Velachery", "lat": 12.981, "lon": 80.221},
        {"name": "MIOT Hospital", "lat": 13.037, "lon": 80.197},
        {"name": "Global Hospital", "lat": 12.894, "lon": 80.202},
    ]

    def __init__(self, hospitals: list[dict] | None = None, user_agent: str = "appointment-ai-hospitals") -> None:
        self.hospitals = list(hospitals) if hospitals is not None else list(self.DEFAULT_HOSPITALS)
        self.geolocator = Nominatim(user_agent=user_agent)

    def _resolve_coordinates(self, location_name, latitude, longitude) -> tuple[float | None, float | None]:
        if latitude is not None and longitude is not None:
            return float(latitude), float(longitude)

        if not location_name:
            return None, None

        try:
            geocoded = self.geolocator.geocode(str(location_name), exactly_one=True, timeout=10)
            if geocoded is not None:
                return float(geocoded.latitude), float(geocoded.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            return None, None

        return None, None

    def find_nearest_hospital(self, coords: dict, hospitals: list[dict] | None = None) -> dict:
        """Tool method: return nearest hospital and distance in km."""
        dataset = hospitals if hospitals is not None else self.hospitals
        if not dataset:
            return {"nearest_hospital": None, "distance_km": None}

        latitude = coords.get("latitude")
        longitude = coords.get("longitude")
        if latitude is None:
            latitude = coords.get("lat")
        if longitude is None:
            longitude = coords.get("lon")

        if latitude is None or longitude is None:
            first = dataset[0]
            return {
                "nearest_hospital": str(first["name"]),
                "distance_km": None,
            }

        patient_point = (float(latitude), float(longitude))
        nearest = min(
            dataset,
            key=lambda hospital: geodesic(patient_point, (hospital["lat"], hospital["lon"])).km,
        )
        distance_km = float(
            geodesic(patient_point, (nearest["lat"], nearest["lon"])).km
        )
        return {
            "nearest_hospital": str(nearest["name"]),
            "distance_km": round(distance_km, 3),
        }

    def allocate(self, request: dict, session_agent, user_id=None) -> dict:
        """Allocate hospital by priority:
        1) previous hospital in session memory,
        2) user preferred hospital,
        3) nearest hospital by coordinates.
        """
        resolved_user_id = user_id
        if resolved_user_id is None:
            resolved_user_id = request.get("id", request.get("name", "Unknown"))

        # 1) Reuse previously assigned hospital for existing users
        existing_session = session_agent.get_session(resolved_user_id)
        previous_hospital = None
        if existing_session:
            previous_hospital = existing_session.get("hospital")

        if previous_hospital:
            return {"assigned_hospital": previous_hospital}

        # 2) Use user preferred hospital when provided
        preferred_hospital = request.get("user_preferred_hospital")
        if preferred_hospital:
            assigned_hospital = str(preferred_hospital)
            session_agent.store_assigned_hospital(resolved_user_id, assigned_hospital)
            return {"assigned_hospital": assigned_hospital}

        # 3) Otherwise assign nearest hospital
        location_name = request.get("location") or request.get("location_name")
        latitude, longitude = self._resolve_coordinates(
            location_name=location_name,
            latitude=request.get("latitude"),
            longitude=request.get("longitude"),
        )

        nearest_result = self.find_nearest_hospital(
            {"latitude": latitude, "longitude": longitude},
            hospitals=self.hospitals,
        )
        assigned_hospital = nearest_result["nearest_hospital"]
        session_agent.store_assigned_hospital(resolved_user_id, assigned_hospital)
        return {"assigned_hospital": assigned_hospital}
