"""LangChain-based scheduling controller that orchestrates agent tools."""

from __future__ import annotations

from datetime import datetime
import json
import os

from agents.cancellation_agent import CancellationAgent
from agents.queue_priority_agent import QueuePriorityAgent

try:
    from langchain.agents import AgentExecutor
    from langchain.agents import create_tool_calling_agent
except ImportError:
    try:
        from langchain.agents import AgentExecutor
        from langchain.agents import create_openai_tools_agent as create_tool_calling_agent
    except ImportError:
        AgentExecutor = None
        create_tool_calling_agent = None

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import StructuredTool
except ImportError:
    ChatPromptTemplate = None
    StructuredTool = None


class LangChainSchedulingController:
    """Orchestrates scheduling tools through LangChain AgentExecutor."""

    def __init__(
        self,
        session_agent,
        location_agent,
        hospital_allocator_agent,
        urgency_agent,
        no_show_agent,
        slot_recommendation_agent,
        default_available_slots: list,
        queue_priority_agent=None,
        cancellation_agent=None,
    ) -> None:
        self.session_agent = session_agent
        self.location_agent = location_agent
        self.hospital_allocator_agent = hospital_allocator_agent
        self.urgency_agent = urgency_agent
        self.no_show_agent = no_show_agent
        self.slot_recommendation_agent = slot_recommendation_agent
        self.queue_priority_agent = queue_priority_agent or QueuePriorityAgent()
        self.cancellation_agent = cancellation_agent or CancellationAgent(
            queue_priority_agent=self.queue_priority_agent
        )
        self.default_available_slots = list(default_available_slots)

        self._tool_state: dict = {}

        self.tools = self._build_tools()
        self.agent_executor = self._build_agent_executor()

    def _build_tools(self) -> list:
        if StructuredTool is None:
            return []

        return [
            StructuredTool.from_function(
                func=self.extract_location,
                name="extract_location",
                description="Extract patient location and coordinates from raw text.",
            ),
            StructuredTool.from_function(
                func=self.classify_urgency,
                name="classify_urgency",
                description="Classify urgency from patient reason into HIGH, MEDIUM, or LOW.",
            ),
            StructuredTool.from_function(
                func=self.predict_no_show,
                name="predict_no_show",
                description=(
                    "Predict no-show probability using features: age, sms_received, "
                    "appointment_hour, days_between_booking."
                ),
            ),
            StructuredTool.from_function(
                func=self.find_nearest_hospital,
                name="find_nearest_hospital",
                description="Find nearest hospital and distance from patient coordinates.",
            ),
            StructuredTool.from_function(
                func=self.recommend_slot,
                name="recommend_slot",
                description=(
                    "Recommend the best slot from available_slots using urgency, distance, "
                    "no-show probability, and preferred time difference scoring."
                ),
            ),
            StructuredTool.from_function(
                func=self.rank_patient_queue,
                name="rank_patient_queue",
                description=(
                    "Rank queued patients by FCFS/urgency and nearest-distance boost when "
                    "a close-time cancellation occurs."
                ),
            ),
            StructuredTool.from_function(
                func=self.handle_cancellation_slot,
                name="handle_cancellation_slot",
                description=(
                    "Handle slot cancellation, rank waiting queue, and return reassigned patient "
                    "based on close-time nearest policy or FCFS."
                ),
            ),
        ]

    def _build_llm(self):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return None

        model_name = os.getenv("SCHEDULER_AGENT_MODEL", "gpt-4o-mini")

        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model_name, temperature=0)
        except ImportError:
            pass

        try:
            from langchain_community.chat_models import ChatOpenAI

            try:
                return ChatOpenAI(model=model_name, temperature=0)
            except TypeError:
                return ChatOpenAI(model_name=model_name, temperature=0)
        except ImportError:
            return None

    def _build_agent_executor(self):
        if AgentExecutor is None or create_tool_calling_agent is None or ChatPromptTemplate is None:
            return None

        llm = self._build_llm()
        if llm is None:
            return None

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an agentic medical appointment scheduler. "
                    "Use tools to compute urgency, location, nearest hospital, no-show probability, "
                    "best slot, queue priority, and cancellation reassignment when needed. "
                    "Always call tools before final answer.",
                ),
                (
                    "human",
                    "Patient payload: {input}\n"
                    "Call tools as needed and return final JSON with keys: "
                    "id, urgency, assigned_hospital, no_show_probability, recommended_slot.",
                ),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        agent = create_tool_calling_agent(llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=False)

    def _parse_payload(self, maybe_json):
        if isinstance(maybe_json, dict):
            return dict(maybe_json)
        if isinstance(maybe_json, str):
            text = maybe_json.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
        return {}

    def _parse_list(self, value):
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [value]
        return []

    @staticmethod
    def _extract_hour(preferred_time, default_hour: int = 10) -> int:
        if preferred_time is None:
            return default_hour

        if isinstance(preferred_time, datetime):
            return int(preferred_time.hour)

        text = str(preferred_time).strip().replace("Z", "")
        formats = [
            "%H:%M",
            "%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                return int(datetime.strptime(text, fmt).hour)
            except ValueError:
                continue

        try:
            return int(datetime.fromisoformat(text).hour)
        except ValueError:
            return default_hour

    @staticmethod
    def _derive_days_between_booking(request: dict) -> int:
        if request.get("days_between_booking") is not None:
            return int(request["days_between_booking"])

        preferred_time = request.get("preferred_time")
        created_at = request.get("created_at")
        if preferred_time is None or created_at is None:
            return 0

        try:
            preferred_dt = datetime.fromisoformat(str(preferred_time).replace("Z", ""))
            created_dt = datetime.fromisoformat(str(created_at).replace("Z", ""))
            delta_days = (preferred_dt.date() - created_dt.date()).days
            return max(0, int(delta_days))
        except ValueError:
            return 0

    def _build_no_show_features(self, request: dict) -> dict:
        preferred_time = request.get("preferred_time")
        appointment_hour = request.get("appointment_hour")
        if appointment_hour is None:
            appointment_hour = self._extract_hour(preferred_time)

        return {
            "age": float(request.get("age", 30)),
            "sms_received": int(request.get("sms_received", 0)),
            "appointment_hour": int(appointment_hour),
            "days_between_booking": int(self._derive_days_between_booking(request)),
        }

    # Tool definitions
    def extract_location(self, raw_text: str) -> dict:
        result = self.location_agent.extract(raw_text)
        self._tool_state["location_result"] = result
        return result

    def classify_urgency(self, reason: str) -> str:
        urgency = self.urgency_agent.classify_urgency(reason)
        self._tool_state["urgency"] = urgency
        return urgency

    def predict_no_show(self, features) -> float:
        parsed_features = self._parse_payload(features)
        if not parsed_features and isinstance(features, dict):
            parsed_features = features

        probability = self.no_show_agent.predict_no_show(parsed_features)
        self._tool_state["no_show_probability"] = probability
        return float(probability)

    def find_nearest_hospital(self, coords) -> dict:
        parsed_coords = self._parse_payload(coords)
        if not parsed_coords and isinstance(coords, dict):
            parsed_coords = coords

        hospital_dataset = parsed_coords.get("hospital_dataset")
        if hospital_dataset is None:
            hospital_dataset = parsed_coords.get("hospitals")

        nearest = self.hospital_allocator_agent.find_nearest_hospital(
            parsed_coords,
            hospitals=hospital_dataset,
        )
        self._tool_state["nearest_hospital"] = nearest
        return nearest

    def recommend_slot(self, patient_data, available_slots) -> str | None:
        parsed_patient_data = self._parse_payload(patient_data)
        if not parsed_patient_data and isinstance(patient_data, dict):
            parsed_patient_data = patient_data

        slots = self._parse_list(available_slots)
        if not slots:
            slots = self.default_available_slots

        recommendation = self.slot_recommendation_agent.recommend_slot(parsed_patient_data, slots)
        self._tool_state["recommended_slot"] = recommendation
        return recommendation

    def rank_patient_queue(self, queue_payload) -> list:
        """Tool method for ranking waiting queue patient IDs."""
        parsed_payload = self._parse_payload(queue_payload)
        if not parsed_payload and isinstance(queue_payload, dict):
            parsed_payload = queue_payload

        ranked_ids = self.queue_priority_agent.rank_queue_from_payload(parsed_payload)
        self._tool_state["ranked_queue"] = ranked_ids
        return ranked_ids

    def handle_cancellation_slot(self, cancellation_payload) -> dict:
        """Tool method for cancellation reassignment decisions."""
        parsed_payload = self._parse_payload(cancellation_payload)
        if not parsed_payload and isinstance(cancellation_payload, dict):
            parsed_payload = cancellation_payload

        available_slots = self._parse_list(
            parsed_payload.get("available_slots", self.default_available_slots)
        )
        waiting_queue = self._parse_list(parsed_payload.get("waiting_queue", parsed_payload.get("queue", [])))

        hospital_coords = parsed_payload.get("hospital_coords", {})
        if isinstance(hospital_coords, str):
            try:
                parsed_coords = json.loads(hospital_coords)
                if isinstance(parsed_coords, dict):
                    hospital_coords = parsed_coords
            except json.JSONDecodeError:
                hospital_coords = {}

        result = self.cancellation_agent.handle_cancellation(
            cancelled_slot=parsed_payload.get("cancelled_slot", parsed_payload.get("slot")),
            available_slots=available_slots,
            waiting_queue=waiting_queue,
            hospital_coords=hospital_coords,
            cancellation_close=bool(parsed_payload.get("cancellation_close", False)),
            payload=parsed_payload,
        )

        self._tool_state["cancellation_result"] = result
        self._tool_state["ranked_queue"] = result.get("ranked_queue", [])
        return result

    def schedule(self, request: dict, available_slots: list | None = None) -> dict:
        self._tool_state = {}

        user_id = request.get("id", request.get("name", "Unknown"))
        name = str(request.get("name", "Unknown"))
        raw_text = str(request.get("raw_text", ""))
        reason = str(request.get("reason") or raw_text)

        self.session_agent.update_request(user_id, request)

        slot_pool = available_slots
        if slot_pool is None:
            slot_pool = request.get("available_slots", self.default_available_slots)
        slot_pool = self._parse_list(slot_pool)
        if not slot_pool:
            slot_pool = list(self.default_available_slots)

        features = self._build_no_show_features(request)

        # Try LLM-based agent orchestration first.
        if self.agent_executor is not None:
            payload = {
                "request": request,
                "available_slots": slot_pool,
                "features": features,
                "hospital_dataset": self.hospital_allocator_agent.hospitals,
            }
            try:
                self.agent_executor.invoke({"input": json.dumps(payload)})
            except Exception:
                # Keep pipeline resilient and fall back to deterministic tool orchestration.
                pass

        cancellation_result = self._tool_state.get("cancellation_result")
        cancellation_event = request.get("cancellation_event")
        has_cancellation_input = (
            request.get("cancelled_slot") is not None
            or isinstance(cancellation_event, dict)
        )
        if has_cancellation_input and not cancellation_result:
            event_payload = dict(cancellation_event) if isinstance(cancellation_event, dict) else {}
            cancellation_payload = {
                "cancelled_slot": request.get("cancelled_slot", event_payload.get("cancelled_slot")),
                "available_slots": slot_pool,
                "waiting_queue": request.get("waiting_queue", event_payload.get("waiting_queue", [])),
                "hospital_coords": request.get("hospital_coords", event_payload.get("hospital_coords", {})),
                "cancellation_close": request.get("cancellation_close", event_payload.get("cancellation_close", False)),
            }
            cancellation_result = self.handle_cancellation_slot(cancellation_payload)

        if cancellation_result is not None:
            updated_slots = cancellation_result.get("updated_available_slots")
            if isinstance(updated_slots, list):
                slot_pool = updated_slots

        # Deterministic fallback and completion for any missing outputs.
        location_result = self._tool_state.get("location_result")
        if not location_result:
            location_result = self.extract_location(raw_text)

        urgency = self._tool_state.get("urgency")
        if not urgency:
            urgency = self.classify_urgency(reason)

        nearest = self._tool_state.get("nearest_hospital")
        if not nearest:
            coords = {
                "latitude": request.get("latitude", location_result.get("latitude")),
                "longitude": request.get("longitude", location_result.get("longitude")),
                "hospitals": self.hospital_allocator_agent.hospitals,
            }
            nearest = self.find_nearest_hospital(coords)

        no_show_probability = self._tool_state.get("no_show_probability")
        if no_show_probability is None:
            no_show_probability = self.predict_no_show(features)

        hospital_result = self.hospital_allocator_agent.allocate(
            {
                "id": request.get("id"),
                "name": name,
                "location": request.get("location") or location_result.get("location"),
                "location_name": location_result.get("location_name"),
                "latitude": request.get("latitude", location_result.get("latitude")),
                "longitude": request.get("longitude", location_result.get("longitude")),
                "user_preferred_hospital": request.get("user_preferred_hospital"),
            },
            session_agent=self.session_agent,
            user_id=user_id,
        )

        patient_data = {
            "preferred_time": request.get("preferred_time"),
            "urgency": urgency,
            "distance_to_hospital": nearest.get("distance_km") or 0.0,
            "no_show_probability": float(no_show_probability),
        }

        recommended_slot = self._tool_state.get("recommended_slot")
        if not recommended_slot:
            recommended_slot = self.recommend_slot(patient_data, slot_pool)

        response = {
            "id": user_id,
            "name": name,
            "urgency": urgency,
            "assigned_hospital": hospital_result["assigned_hospital"],
            "no_show_probability": round(float(no_show_probability), 2),
            "recommended_slot": recommended_slot,
            "location_name": location_result.get("location_name"),
            "location": location_result.get("location"),
            "latitude": location_result.get("latitude"),
            "longitude": location_result.get("longitude"),
            "nearest_hospital": nearest.get("nearest_hospital"),
            "distance_km": nearest.get("distance_km"),
        }

        if cancellation_result is not None:
            response["cancellation_reassignment"] = cancellation_result

        return response
