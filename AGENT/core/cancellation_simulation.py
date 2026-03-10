"""Simulate an appointment cancellation and updated slot recommendation."""

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.cancellation_agent import CancellationAgent
from agents.slot_agent import SlotRecommendationAgent


def simulate_cancellation() -> None:
    available_slots = ["09:00", "11:00", "14:00", "16:00"]
    preferred_time = "10:00"
    urgency = "HIGH"

    waiting_queue = [
        {"id": 5, "waiting_time": 30, "urgency": "MEDIUM", "latitude": 12.981, "longitude": 80.220},
        {"id": 8, "waiting_time": 40, "urgency": "LOW", "latitude": 13.050, "longitude": 80.200},
    ]
    hospital_coords = {"latitude": 12.981, "longitude": 80.221}

    slot_agent = SlotRecommendationAgent()
    cancellation_agent = CancellationAgent()

    # Initial recommendation before cancellation
    original_recommendation = slot_agent.recommend(
        preferred_time=preferred_time,
        urgency=urgency,
        available_slots=available_slots,
    )

    # 1) Detect cancelled slot
    cancelled_slot = "10:00"
    print(f"Detected cancelled slot: {cancelled_slot}")

    # 2) Call CancellationAgent
    # 3) Update available slots and assign from queue
    cancellation_result = cancellation_agent.handle_cancellation(
        cancelled_slot=cancelled_slot,
        available_slots=available_slots,
        waiting_queue=waiting_queue,
        hospital_coords=hospital_coords,
        cancellation_close=True,
    )

    updated_slots = cancellation_result["updated_available_slots"]

    # 4) Re-run slot recommendation
    updated_recommendation = slot_agent.recommend(
        preferred_time=preferred_time,
        urgency=urgency,
        available_slots=updated_slots,
    )

    # 5) Print updated slot decision
    print(f"Original recommendation: {original_recommendation}")
    print(f"Cancellation reassignment: {cancellation_result}")
    print(f"Updated available slots: {updated_slots}")
    print(f"Updated slot decision: {updated_recommendation}")


if __name__ == "__main__":
    simulate_cancellation()
