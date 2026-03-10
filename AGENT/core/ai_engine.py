"""Agentic AI pipeline orchestration for appointment handling."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.cancellation_agent import CancellationAgent
from agents.hospital_allocator_agent import HospitalAllocationAgent
from agents.location_agent import LocationAgent
from agents.noshow_agent import NoShowAgent
from agents.queue_priority_agent import QueuePriorityAgent
from agents.session_agent import SessionAgent
from agents.slot_agent import SlotRecommendationAgent
from agents.urgency_agent import UrgencyAgent
from core.langchain_controller import LangChainSchedulingController


class AgenticAIEngine:
    """Runs the scheduling pipeline with a LangChain tool-using controller."""

    def __init__(self, available_slots: list | None = None) -> None:
        self.available_slots = available_slots or ["09:00", "10:00", "11:00", "14:00", "16:00"]

        # Core agents
        self.session_agent = SessionAgent()
        self.location_agent = LocationAgent()
        self.hospital_allocator_agent = HospitalAllocationAgent()
        self.urgency_agent = UrgencyAgent()
        self.noshow_agent = NoShowAgent()
        self.slot_recommendation_agent = SlotRecommendationAgent()
        self.queue_priority_agent = QueuePriorityAgent()
        self.cancellation_agent = CancellationAgent(queue_priority_agent=self.queue_priority_agent)

        # LangChain orchestration layer
        self.agent_controller = LangChainSchedulingController(
            session_agent=self.session_agent,
            location_agent=self.location_agent,
            hospital_allocator_agent=self.hospital_allocator_agent,
            urgency_agent=self.urgency_agent,
            no_show_agent=self.noshow_agent,
            slot_recommendation_agent=self.slot_recommendation_agent,
            queue_priority_agent=self.queue_priority_agent,
            cancellation_agent=self.cancellation_agent,
            default_available_slots=self.available_slots,
        )

    def run(self, request: dict, available_slots: list | None = None) -> dict:
        """Primary pipeline entrypoint."""
        return self.agent_controller.schedule(request=request, available_slots=available_slots)

    def process(self, request: dict) -> dict:
        """Backward-compatible alias for pipeline execution."""
        return self.run(request)


class AIEngine(AgenticAIEngine):
    """Backward-compatible name for existing imports."""
