"""Queue priority agent for ranking waiting patients."""

from geopy.distance import geodesic


class QueuePriorityAgent:
    """Ranks patient queue entries for slot allocation decisions."""

    def __init__(
        self,
        wait_time_weight: float = 1.0,
        urgency_weight: float = 2.0,
        distance_weight: float = 1.0,
    ) -> None:
        self.wait_time_weight = float(wait_time_weight)
        self.urgency_weight = float(urgency_weight)
        self.distance_weight = float(distance_weight)

    def _urgency_level(self, urgency: str) -> int:
        mapping = {
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1,
        }
        return mapping.get(str(urgency).strip().upper(), 1)

    def _extract_coords(self, patient: dict) -> tuple[float | None, float | None]:
        latitude = patient.get("latitude", patient.get("lat"))
        longitude = patient.get("longitude", patient.get("lon"))

        if latitude is None and isinstance(patient.get("coords"), dict):
            latitude = patient["coords"].get("latitude", patient["coords"].get("lat"))
        if longitude is None and isinstance(patient.get("coords"), dict):
            longitude = patient["coords"].get("longitude", patient["coords"].get("lon"))

        if latitude is None or longitude is None:
            return None, None

        return float(latitude), float(longitude)

    def _distance_km(self, patient: dict, hospital_coords: dict) -> float | None:
        patient_lat, patient_lon = self._extract_coords(patient)
        hospital_lat = hospital_coords.get("latitude", hospital_coords.get("lat"))
        hospital_lon = hospital_coords.get("longitude", hospital_coords.get("lon"))

        if patient_lat is None or patient_lon is None:
            return None
        if hospital_lat is None or hospital_lon is None:
            return None

        return float(
            geodesic((patient_lat, patient_lon), (float(hospital_lat), float(hospital_lon))).km
        )

    def _priority_score(self, waiting_time: float, urgency_level: float, distance_km: float | None) -> float:
        inverse_distance = 0.0
        if distance_km is not None:
            inverse_distance = 1.0 / (1.0 + max(distance_km, 0.0))

        return (
            (self.wait_time_weight * waiting_time)
            + (self.urgency_weight * urgency_level)
            + (self.distance_weight * inverse_distance)
        )

    def rank_queue(
        self,
        patient_queue: list[dict],
        hospital_coords: dict,
        cancellation_close: bool = False,
        use_scoring: bool = False,
    ) -> list:
        """Return patient IDs sorted by priority (highest first)."""
        if not patient_queue:
            return []

        indexed_queue = list(enumerate(patient_queue))

        # Rule: default policy -> First Come First Serve
        if not cancellation_close and not use_scoring:
            return [
                patient.get("id")
                for _, patient in indexed_queue
                if patient.get("id") is not None
            ]

        # Rule: if cancellation is close to slot time -> nearest patient first
        if cancellation_close:
            def nearest_sort_key(item):
                fcfs_index, patient = item
                distance_km = self._distance_km(patient, hospital_coords)
                if distance_km is None:
                    distance_km = float("inf")
                urgency_level = self._urgency_level(patient.get("urgency", "LOW"))
                wait_time = float(patient.get("waiting_time", 0.0))
                # Primary: nearest distance, then urgency, then waiting_time, then FCFS.
                return (distance_km, -urgency_level, -wait_time, fcfs_index)

            nearest_sorted = sorted(indexed_queue, key=nearest_sort_key)
            return [
                patient.get("id")
                for _, patient in nearest_sorted
                if patient.get("id") is not None
            ]

        # Optional scoring policy for broader queue-ranking use cases.
        scored = []
        for fcfs_index, patient in indexed_queue:
            wait_time = float(patient.get("waiting_time", 0.0))
            urgency_level = float(self._urgency_level(patient.get("urgency", "LOW")))
            distance_km = self._distance_km(patient, hospital_coords)

            priority_score = self._priority_score(wait_time, urgency_level, distance_km)
            scored.append(
                {
                    "id": patient.get("id"),
                    "priority_score": float(priority_score),
                    "fcfs_index": fcfs_index,
                }
            )

        scored.sort(key=lambda item: (item["priority_score"], -item["fcfs_index"]), reverse=True)
        return [item["id"] for item in scored if item.get("id") is not None]

    def rank_queue_from_payload(self, payload: dict) -> list:
        """Tool-friendly wrapper for LangChain structured input."""
        patient_queue = payload.get("patient_queue", payload.get("queue", []))
        hospital_coords = payload.get("hospital_coords", {})
        cancellation_close = bool(payload.get("cancellation_close", False))
        use_scoring = bool(payload.get("use_scoring", False))

        return self.rank_queue(
            patient_queue=patient_queue,
            hospital_coords=hospital_coords,
            cancellation_close=cancellation_close,
            use_scoring=use_scoring,
        )
