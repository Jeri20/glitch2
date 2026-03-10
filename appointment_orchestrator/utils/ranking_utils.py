"""Ranking utilities for waitlist prioritization."""

from typing import Dict, List


def calculate_waitlist_score(entry: Dict) -> float:
    """
    Calculate priority score for a waitlist entry.

    score = (wait_hours * 0.5) + (urgency * 30) - (distance_km * 2)
    If distance is missing, distance term is skipped.
    """
    wait_hours = float(entry.get("wait_hours", 0))
    urgency = int(entry.get("urgency", 0))
    distance_km = entry.get("distance_km")
    score = (wait_hours * 0.5) + (urgency * 30)
    if distance_km is not None:
        score -= float(distance_km) * 2
    return score


def rank_waitlist(entries: List[Dict]) -> List[Dict]:
    """Compute score, attach it to each entry, and sort descending by score."""
    ranked: List[Dict] = []
    for entry in entries:
        enriched = dict(entry)
        enriched["score"] = round(calculate_waitlist_score(entry), 2)
        ranked.append(enriched)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
