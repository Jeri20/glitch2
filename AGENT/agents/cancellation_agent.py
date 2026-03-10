"""Cancellation handling agent."""

from agents.queue_priority_agent import QueuePriorityAgent


class CancellationAgent:
    """Handles cancellation checks and slot reassignment via queue priority."""

    def __init__(self, queue_priority_agent: QueuePriorityAgent | None = None) -> None:
        self.queue_priority_agent = queue_priority_agent or QueuePriorityAgent()

    def should_cancel(self, reason: str) -> bool:
        return bool(reason and reason.strip())

    def detect_cancelled_slot(self, cancelled_slot=None, payload: dict | None = None):
        """Step 1: detect cancelled slot from direct value or payload."""
        if cancelled_slot is not None:
            return cancelled_slot

        if payload:
            for key in ("cancelled_slot", "slot", "appointment_slot"):
                value = payload.get(key)
                if value is not None:
                    return value

        return None

    def retrieve_waiting_queue(self, waiting_queue=None, payload: dict | None = None) -> list:
        """Step 2: retrieve waiting queue list."""
        if waiting_queue is not None:
            return list(waiting_queue)

        if payload:
            queue_value = payload.get("waiting_queue", payload.get("queue", []))
            if isinstance(queue_value, list):
                return list(queue_value)

        return []

    def handle_cancellation(
        self,
        cancelled_slot=None,
        available_slots=None,
        waiting_queue=None,
        hospital_coords=None,
        cancellation_close: bool = False,
        payload: dict | None = None,
    ) -> dict:
        """Handle cancellation and return reassignment decision.

        Rules:
        - If cancellation is close to appointment time: prioritize nearest patient.
        - Otherwise: follow FCFS.
        """
        # 1) Detect cancelled slot.
        slot = self.detect_cancelled_slot(cancelled_slot=cancelled_slot, payload=payload)
        if slot is None:
            raise ValueError("Cancelled slot is required for cancellation handling.")

        # Update available slots with cancelled slot.
        updated_available_slots = list(available_slots) if available_slots is not None else []
        if slot not in updated_available_slots:
            updated_available_slots.append(slot)

        # 2) Retrieve waiting queue.
        queue = self.retrieve_waiting_queue(waiting_queue=waiting_queue, payload=payload)

        # 3) Rank patients using QueuePriorityAgent.
        ranked_ids = self.queue_priority_agent.rank_queue(
            patient_queue=queue,
            hospital_coords=hospital_coords or {},
            cancellation_close=bool(cancellation_close),
            use_scoring=False,
        )

        reassigned_patient_id = ranked_ids[0] if ranked_ids else None

        # If reassigned immediately, slot is no longer free.
        if reassigned_patient_id is not None:
            try:
                updated_available_slots.remove(slot)
            except ValueError:
                pass

        return {
            "slot": slot,
            "reassigned_patient_id": reassigned_patient_id,
            "ranked_queue": ranked_ids,
            "updated_available_slots": updated_available_slots,
            "cancellation_close": bool(cancellation_close),
        }
