"""Distance calculation helpers."""

import math
from typing import Dict, Optional


def manhattan_distance(point_a: Dict[str, float], point_b: Dict[str, float]) -> float:
    """Calculate Manhattan distance for two coordinate points."""
    return abs(float(point_a["lat"]) - float(point_b["lat"])) + abs(
        float(point_a["lon"]) - float(point_b["lon"])
    )


def haversine_distance_km(point_a: Dict[str, float], point_b: Dict[str, float]) -> float:
    """Calculate Haversine distance in kilometers between two geo points."""
    lat1 = math.radians(float(point_a["lat"]))
    lon1 = math.radians(float(point_a["lon"]))
    lat2 = math.radians(float(point_b["lat"]))
    lon2 = math.radians(float(point_b["lon"]))

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    earth_radius_km = 6371.0
    return 2 * earth_radius_km * math.asin(math.sqrt(h))


def calculate_distance_km(
    point_a: Optional[Dict[str, float]],
    point_b: Optional[Dict[str, float]],
    method: str = "haversine",
) -> Optional[float]:
    """Calculate distance with selected method; returns None if coordinates are missing."""
    if not point_a or not point_b:
        return None
    if "lat" not in point_a or "lon" not in point_a or "lat" not in point_b or "lon" not in point_b:
        return None
    if method == "manhattan":
        return manhattan_distance(point_a, point_b)
    return haversine_distance_km(point_a, point_b)

