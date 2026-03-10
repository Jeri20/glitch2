"""Slot recommendation agents."""

from datetime import date, datetime


class SlotRecommendationAgent:
    """Score-based slot recommender combining urgency, distance, no-show, and time match."""

    def __init__(
        self,
        urgency_weight: float = 0.4,
        distance_weight: float = 0.2,
        no_show_weight: float = 0.2,
        time_weight: float = 0.2,
    ) -> None:
        self.urgency_weight = urgency_weight
        self.distance_weight = distance_weight
        self.no_show_weight = no_show_weight
        self.time_weight = time_weight

    def _to_datetime(self, value) -> datetime:
        if isinstance(value, datetime):
            return value

        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())

        if isinstance(value, str):
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1]

            formats = [
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%dT%H:%M:%S",
                "%H:%M",
            ]

            for fmt in formats:
                try:
                    parsed = datetime.strptime(text, fmt)
                    if fmt == "%H:%M":
                        return datetime.combine(date.today(), parsed.time())
                    return parsed
                except ValueError:
                    continue

            try:
                return datetime.fromisoformat(text)
            except ValueError as err:
                raise ValueError(f"Unsupported slot time format: {value}") from err

        raise TypeError(f"Unsupported slot value type: {type(value)!r}")

    def _urgency_score(self, urgency: str) -> float:
        lookup = {
            "HIGH": 1.0,
            "MEDIUM": 0.6,
            "LOW": 0.3,
        }
        return lookup.get(str(urgency).strip().upper(), 0.3)

    def _inverse_distance(self, distance_km: float) -> float:
        bounded_distance = max(0.0, float(distance_km))
        return 1.0 / (1.0 + bounded_distance)

    def _preferred_time_match(self, slot_dt: datetime, preferred_dt: datetime | None) -> float:
        if preferred_dt is None:
            return 0.5

        diff_minutes = abs((slot_dt - preferred_dt).total_seconds()) / 60.0
        # Full score when exact match, linearly decreasing to 0 at 12 hours difference.
        return max(0.0, 1.0 - (diff_minutes / 720.0))

    def recommend_slot(self, patient_data: dict, available_slots: list) -> str | None:
        """Tool method: return the highest-scoring slot."""
        if not available_slots:
            return None

        preferred_time = patient_data.get("preferred_time")
        urgency = patient_data.get("urgency", "LOW")
        no_show_probability = float(patient_data.get("no_show_probability", 0.0))
        distance_to_hospital = float(patient_data.get("distance_to_hospital", 0.0))

        preferred_dt = None
        if preferred_time is not None:
            preferred_dt = self._to_datetime(preferred_time)

        urgency_score = self._urgency_score(urgency)
        inverse_distance = self._inverse_distance(distance_to_hospital)

        best_slot = None
        best_score = float("-inf")

        for slot in available_slots:
            slot_dt = self._to_datetime(slot)
            preferred_time_match = self._preferred_time_match(slot_dt, preferred_dt)

            # score =
            # (urgency_weight * urgency_score)
            # + (distance_weight * inverse_distance)
            # + (no_show_weight * (1 - no_show_probability))
            # + (time_weight * preferred_time_match)
            score = (
                (self.urgency_weight * urgency_score)
                + (self.distance_weight * inverse_distance)
                + (self.no_show_weight * (1.0 - no_show_probability))
                + (self.time_weight * preferred_time_match)
            )

            if score > best_score:
                best_score = score
                best_slot = slot

        return best_slot

    def recommend(
        self,
        preferred_time=None,
        urgency: str = "LOW",
        available_slots: list | None = None,
        patient_data: dict | None = None,
    ):
        """Backward-compatible wrapper used by existing pipeline code."""
        slots = available_slots or []
        if patient_data is None:
            patient_data = {
                "preferred_time": preferred_time,
                "urgency": urgency,
                "distance_to_hospital": 0.0,
                "no_show_probability": 0.0,
            }

        return self.recommend_slot(patient_data=patient_data, available_slots=slots)


class SlotAgent:
    """Backward-compatible wrapper around SlotRecommendationAgent."""

    def __init__(self) -> None:
        self.recommender = SlotRecommendationAgent()

    def choose_slot(self, slots: list, preferred_time=None, urgency: str = "LOW"):
        return self.recommender.recommend(preferred_time, urgency, slots)
