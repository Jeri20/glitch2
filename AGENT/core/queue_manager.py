"""Queue simulation for processing multiple patient requests."""

from collections import deque
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from agents.queue_priority_agent import QueuePriorityAgent
    from core.ai_engine import AIEngine
else:
    from agents.queue_priority_agent import QueuePriorityAgent
    from .ai_engine import AIEngine


class QueueManager:
    """FIFO queue manager for patient scheduling simulation."""

    def __init__(self, engine: AIEngine | None = None, available_slots: list | None = None) -> None:
        # 1) Create queue
        self.request_queue = deque()
        self.processed_results = deque()

        self.engine = engine or AIEngine()
        self.queue_priority_agent = getattr(self.engine, "queue_priority_agent", QueuePriorityAgent())

        self.available_slots = available_slots or [
            "2026-03-10T09:00:00",
            "2026-03-10T09:30:00",
            "2026-03-10T10:00:00",
            "2026-03-10T10:30:00",
            "2026-03-10T11:00:00",
        ]

    def add_request(self, request: dict) -> None:
        self.request_queue.append(request)

    def add_requests(self, requests: list[dict]) -> None:
        for request in requests:
            self.add_request(request)

    def get_next_request(self) -> dict | None:
        if not self.request_queue:
            return None
        return self.request_queue.popleft()

    def process_all(self) -> list[dict]:
        """Process each queued request through AI engine and print key results."""
        results = []
        while self.request_queue:
            request = self.get_next_request()
            if request is None:
                break

            # 2) Process each through ai_engine
            result = self.engine.run(request, available_slots=self.available_slots)

            # 3) Store processed outputs in queue-like collection
            self.processed_results.append(result)
            results.append(result)

            # Print required fields for each patient
            print(
                f"Patient {result.get('id')}: "
                f"hospital={result.get('assigned_hospital')}, "
                f"urgency={result.get('urgency')}, "
                f"recommended_slot={result.get('recommended_slot')}"
            )

        return results

    def _resolve_hospital_coords(self, hospital_name: str | None) -> dict:
        if hospital_name is None:
            return {}

        hospitals = getattr(self.engine.hospital_allocator_agent, "hospitals", [])
        for hospital in hospitals:
            if hospital.get("name") == hospital_name:
                return {
                    "latitude": hospital.get("lat"),
                    "longitude": hospital.get("lon"),
                }

        return {}

    def _build_waiting_queue(self) -> list[dict]:
        waiting_queue = []
        for index, result in enumerate(list(self.processed_results)):
            waiting_queue.append(
                {
                    "id": result.get("id"),
                    "urgency": result.get("urgency", "LOW"),
                    "waiting_time": 10 + (index * 5),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                }
            )
        return waiting_queue

    def simulate_cancellation(
        self,
        cancelled_slot: str = "2026-03-10T09:00:00",
        cancellation_close: bool = True,
    ) -> dict:
        """Simulate a cancellation and reallocate slot using QueuePriorityAgent."""
        # 4) Simulate at least one cancellation event
        print(f"Detected cancellation for slot: {cancelled_slot}")

        if cancelled_slot not in self.available_slots:
            self.available_slots.append(cancelled_slot)

        waiting_queue = self._build_waiting_queue()

        hospital_name = None
        if self.processed_results:
            hospital_name = self.processed_results[0].get("assigned_hospital")

        hospital_coords = self._resolve_hospital_coords(hospital_name)

        # 5) Reallocate slot using QueuePriorityAgent
        ranked_ids = self.queue_priority_agent.rank_queue(
            patient_queue=waiting_queue,
            hospital_coords=hospital_coords,
            cancellation_close=cancellation_close,
            use_scoring=False,
        )

        reassigned_patient_id = ranked_ids[0] if ranked_ids else None

        if reassigned_patient_id is not None and cancelled_slot in self.available_slots:
            self.available_slots.remove(cancelled_slot)

        result = {
            "slot": cancelled_slot,
            "reassigned_patient_id": reassigned_patient_id,
            "ranked_queue": ranked_ids,
            "updated_available_slots": list(self.available_slots),
        }

        print(f"Cancellation reassignment: {result}")
        return result


def build_sample_requests() -> list[dict]:
    """Generate 10 sample patient inputs with varied locations and symptoms."""
    return [
        {
            "id": 1,
            "name": "Ravi",
            "preferred_time": "2026-03-10T09:00:00",
            "reason": "chest pain",
            "raw_text": "Hi I am in Velachery and have chest pain",
            "created_at": "2026-03-09T08:00:00",
            "age": 45,
            "sms_received": 1,
        },
        {
            "id": 2,
            "name": "Anita",
            "preferred_time": "2026-03-10T10:30:00",
            "reason": "fever and cough",
            "raw_text": "I live in Adyar and have fever and cough",
            "created_at": "2026-03-09T08:10:00",
            "age": 31,
            "sms_received": 1,
        },
        {
            "id": 3,
            "name": "Vikram",
            "preferred_time": "2026-03-10T11:00:00",
            "reason": "vomiting",
            "raw_text": "From Tambaram with vomiting",
            "created_at": "2026-03-09T08:20:00",
            "age": 38,
            "sms_received": 0,
        },
        {
            "id": 4,
            "name": "Sneha",
            "preferred_time": "2026-03-10T09:30:00",
            "reason": "headache",
            "raw_text": "I am in Anna Nagar with severe headache",
            "created_at": "2026-03-09T08:30:00",
            "age": 26,
            "sms_received": 1,
        },
        {
            "id": 5,
            "name": "Arjun",
            "preferred_time": "2026-03-10T10:00:00",
            "reason": "severe breathing difficulty",
            "raw_text": "My location is Guindy and I have severe breathing difficulty",
            "created_at": "2026-03-09T08:40:00",
            "age": 60,
            "sms_received": 0,
        },
        {
            "id": 6,
            "name": "Meera",
            "preferred_time": "2026-03-10T09:00:00",
            "reason": "routine checkup",
            "raw_text": "I am near Mylapore for routine checkup",
            "created_at": "2026-03-09T08:50:00",
            "age": 50,
            "sms_received": 1,
        },
        {
            "id": 7,
            "name": "Kiran",
            "preferred_time": "2026-03-10T10:30:00",
            "reason": "consultation",
            "raw_text": "From Porur need consultation",
            "created_at": "2026-03-09T09:00:00",
            "age": 28,
            "sms_received": 0,
        },
        {
            "id": 8,
            "name": "Priya",
            "preferred_time": "2026-03-10T11:00:00",
            "reason": "heart attack symptoms",
            "raw_text": "In T Nagar and feeling heart attack symptoms",
            "created_at": "2026-03-09T09:10:00",
            "age": 57,
            "sms_received": 0,
        },
        {
            "id": 9,
            "name": "Nikhil",
            "preferred_time": "2026-03-10T09:30:00",
            "reason": "sore throat",
            "raw_text": "I stay in OMR and have sore throat",
            "created_at": "2026-03-09T09:20:00",
            "age": 24,
            "sms_received": 1,
        },
        {
            "id": 10,
            "name": "Divya",
            "preferred_time": "2026-03-10T10:00:00",
            "reason": "migraine",
            "raw_text": "From Kodambakkam with migraine",
            "created_at": "2026-03-09T09:30:00",
            "age": 42,
            "sms_received": 1,
        },
    ]


def main() -> None:
    try:
        queue_manager = QueueManager()
    except (FileNotFoundError, RuntimeError) as err:
        print(f"Unable to start queue simulation: {err}")
        return

    # 1) Generate 10 sample patient inputs
    sample_requests = build_sample_requests()

    # 3) Store them in a queue
    queue_manager.add_requests(sample_requests)

    # 2) Process each through ai_engine
    queue_manager.process_all()

    # 4 & 5) Simulate cancellation and slot reallocation
    queue_manager.simulate_cancellation(
        cancelled_slot="2026-03-10T09:00:00",
        cancellation_close=True,
    )


if __name__ == "__main__":
    main()
