from flask import Flask, request, jsonify, render_template
from speech_to_text import transcribe_voice
from extractor import extract_appointment, extract_data
from datetime import datetime, timedelta
import json
from pathlib import Path

# Integrated systems from AGENT and agentai
from AGENT.core.ai_engine import AIEngine
from appointment_orchestrator.orchestrator.appointment_orchestrator import (
    AppointmentOrchestrator,
    reset_system_state,
)

app = Flask(__name__)

# Initialize integrations
ai_engine = AIEngine()
orchestrator = AppointmentOrchestrator()
BOOKING_REGISTRY_PATH = Path("appointments.json")
REQUIRED_APPOINTMENT_FIELDS = ("name", "location", "preferred_time", "reason")
INTAKE_SESSIONS = {}


def _first_non_empty(*values):
    """Return the first non-empty value from the provided candidates."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _normalize_preferred_time_for_booking(value):
    """Convert extractor/AI time into HH:MM format expected by booking lookup."""
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(text, fmt).strftime("%H:%M")
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "")).strftime("%H:%M")
        except ValueError:
            return text
    return str(value)


def _build_booking_feedback(booking_result):
    """Return user-facing booking status text."""
    success = bool((booking_result or {}).get("success"))
    slot = (booking_result or {}).get("slot") or {}
    slot_label = " ".join([str(slot.get("date", "")).strip(), str(slot.get("time", "")).strip()]).strip()

    if success:
        if slot_label:
            return f"Slot booked: {slot_label}."
        return "Slot booked."

    message = str((booking_result or {}).get("message", "")).lower()
    if "no slots available" in message:
        return "Slot not available. Added to waitlist."
    if "not available" in message:
        return "Requested slot not available."
    return "Slot not available."


def _is_missing_value(value):
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _slot_label_to_iso(slot_label):
    """Map morning/afternoon/evening to a default ISO datetime (tomorrow)."""
    if not slot_label:
        return None
    label = str(slot_label).strip().lower()
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)

    hour_map = {"morning": 9, "afternoon": 15, "evening": 18}
    if label not in hour_map:
        return None
    return tomorrow.replace(hour=hour_map[label], minute=0, second=0, microsecond=0).isoformat()


def _build_missing_info_prompt(missing_fields):
    prompts = []
    if "name" in missing_fields:
        prompts.append("May I know your name?")
    if "location" in missing_fields:
        prompts.append("Which area are you in?")
    if "preferred_time" in missing_fields:
        prompts.append("What time do you prefer (morning, afternoon, evening)?")
    if "reason" in missing_fields:
        prompts.append("What is your main symptom or reason for the visit?")
    if not prompts:
        return None
    return "I need a few more details before booking your appointment. " + " ".join(prompts)


def _parse_appointment_from_text(text, source, fallback_name=None):
    """
    Parse text into a structured appointment draft without triggering scheduling.
    """
    extracted = extract_appointment(text or "", source)
    generic = extract_data(text or "")
    if not isinstance(generic, dict):
        generic = {"location": None, "preferred_slot": None, "symptoms": []}

    name = extracted.get("name")
    if _is_missing_value(name) and fallback_name and str(fallback_name).strip().lower() not in {
        "demo user",
        "unknown",
    }:
        name = fallback_name

    location = _first_non_empty(extracted.get("location"), generic.get("location"))
    preferred_time = extracted.get("preferred_time")
    if _is_missing_value(preferred_time):
        preferred_time = _slot_label_to_iso(generic.get("preferred_slot"))

    reason = extracted.get("reason")
    symptoms = generic.get("symptoms") or []
    if _is_missing_value(reason) and symptoms:
        reason = ", ".join(symptoms)

    return {
        "name": name,
        "location": location,
        "preferred_time": preferred_time,
        "reason": reason,
        "source": source,
        "raw_text": text or "",
        "extracted": extracted,
        "generic": generic,
    }


def _merge_appointment_drafts(existing, incoming):
    """Merge incoming parsed values into existing draft; incoming non-empty values win."""
    merged = dict(existing or {})
    incoming = dict(incoming or {})

    for field in REQUIRED_APPOINTMENT_FIELDS:
        incoming_value = incoming.get(field)
        if not _is_missing_value(incoming_value):
            merged[field] = incoming_value

    merged["source"] = incoming.get("source") or merged.get("source")
    merged["raw_text"] = " ".join(
        [part for part in [merged.get("raw_text", ""), incoming.get("raw_text", "")] if str(part).strip()]
    ).strip()
    merged["extracted"] = incoming.get("extracted") or merged.get("extracted") or {}
    merged["generic"] = incoming.get("generic") or merged.get("generic") or {}
    return merged


def _validate_required_fields(appointment_draft):
    missing_fields = [
        field for field in REQUIRED_APPOINTMENT_FIELDS if _is_missing_value((appointment_draft or {}).get(field))
    ]
    return missing_fields


def _extract_date_time_parts(value):
    """Return (date, HH:MM) from several time formats."""
    if not value:
        return None, None
    text = str(value).strip().replace("Z", "")
    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%H:%M:%S",
        "%H:%M",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if "Y" in fmt:
                return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")
            return None, parsed.strftime("%H:%M")
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")
    except ValueError:
        return None, text


def _build_slot_allocation_result(appointment):
    """
    Build slot allocation result in the requested call-simulation shape:
    confirmed | waitlist | alternative.
    """
    booking_success = bool((appointment or {}).get("booking_success"))
    booked_slot = (appointment or {}).get("booked_slot") or {}
    preferred_date, preferred_time = _extract_date_time_parts((appointment or {}).get("preferred_time"))
    booked_date = booked_slot.get("date")
    booked_time = booked_slot.get("time")

    if booking_success and booked_date and booked_time:
        booked_iso = f"{booked_date}T{booked_time}:00"
        if preferred_date and preferred_time and (
            booked_date != preferred_date or booked_time != preferred_time
        ):
            return {"status": "alternative", "slot": booked_iso}
        return {"status": "confirmed", "slot": booked_iso}

    booking_status = str((appointment or {}).get("booking_status", "")).lower()
    if "waitlist" in booking_status or "no slots available" in booking_status:
        return {"status": "waitlist"}
    return {"status": "waitlist"}


def _build_call_response_text(slot_result):
    """Generate voice-assistant response message for call simulation."""
    status = (slot_result or {}).get("status")
    slot = (slot_result or {}).get("slot")
    if status == "confirmed" and slot:
        return f"Your appointment has been confirmed for {slot}."
    if status == "alternative" and slot:
        return (
            f"The requested slot is unavailable. "
            f"The next available slot is {slot}. Would you like to book it?"
        )
    return "Sorry, the requested slot is full. You have been added to the waitlist."


def _load_booking_registry():
    if not BOOKING_REGISTRY_PATH.exists():
        return []
    try:
        with BOOKING_REGISTRY_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
            if isinstance(payload, list):
                return payload
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_booking_registry(records):
    with BOOKING_REGISTRY_PATH.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)


def _register_booking(sender, incoming_name, source, raw_text, appointment):
    """Persist successful bookings so users can cancel later with 'cancel'."""
    if not appointment.get("booking_success"):
        return

    slot = appointment.get("booked_slot") or {}
    slot_id = slot.get("slot_id")
    if slot_id is None:
        return

    records = _load_booking_registry()
    record_id = (max([int(item.get("id", 0)) for item in records], default=0) + 1)
    records.append(
        {
            "id": record_id,
            "sender": sender,
            "name": incoming_name or appointment.get("name"),
            "source": source,
            "raw_text": raw_text,
            "patient_id": appointment.get("patient_id"),
            "slot_id": int(slot_id),
            "doctor_id": slot.get("doctor_id"),
            "date": slot.get("date"),
            "time": slot.get("time"),
            "status": "booked",
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    _save_booking_registry(records)


def _find_latest_active_booking(sender):
    if not sender:
        return None
    records = _load_booking_registry()
    for record in reversed(records):
        if str(record.get("sender")) == str(sender) and record.get("status") == "booked":
            return record
    return None


def _mark_booking_cancelled(record_id):
    records = _load_booking_registry()
    for record in records:
        if int(record.get("id", -1)) == int(record_id):
            record["status"] = "cancelled"
            record["cancelled_at"] = datetime.utcnow().isoformat()
            _save_booking_registry(records)
            return


def _is_cancel_intent(text):
    if not text:
        return False
    normalized = str(text).strip().lower()
    direct = {"cancel", "cancel slot", "cancel booking", "cancel appointment"}
    return normalized in direct or normalized.startswith("cancel ")


def _cancel_latest_booking(sender):
    booking = _find_latest_active_booking(sender)
    if not booking:
        return {
            "success": False,
            "message": "I could not find an active booked slot to cancel.",
            "slot": None,
        }

    slot_id = int(booking["slot_id"])
    cancel_result = orchestrator.calendar_service.cancel_appointment(slot_id=slot_id)
    if cancel_result.get("success"):
        _mark_booking_cancelled(booking["id"])
        slot = cancel_result.get("slot") or {}
        label = " ".join([str(slot.get("date", "")).strip(), str(slot.get("time", "")).strip()]).strip()
        message = f"Your appointment is cancelled{': ' + label if label else '.'}"
        return {"success": True, "message": message, "slot": slot}

    message_text = str(cancel_result.get("message", "")).lower()
    if "only booked slots can be cancelled" in message_text or "slot not found" in message_text:
        _mark_booking_cancelled(booking["id"])

    return {
        "success": False,
        "message": cancel_result.get("message", "Could not cancel the booked slot."),
        "slot": cancel_result.get("slot"),
    }


def _store_appointment_from_structured(appointment_draft):
    """
    Execute scheduling only after required fields are complete.
    """
    source = (appointment_draft or {}).get("source", "unknown")
    text = (appointment_draft or {}).get("raw_text", "")

    # 1. Ask the AI engine to parse, classify, and recommend slots
    import random
    request_data = {
        "id": str(random.randint(10000, 99999)),
        "raw_text": text or "",
        "source": source
    }
    ai_result = ai_engine.run(request_data)

    name = _first_non_empty((appointment_draft or {}).get("name"), ai_result.get("name"), "Unknown")
    preferred_time = _first_non_empty(
        (appointment_draft or {}).get("preferred_time"),
        ai_result.get("preferred_time"),
        ai_result.get("recommended_slot"),
    )
    preferred_time_for_booking = _normalize_preferred_time_for_booking(preferred_time)
    reason = _first_non_empty(
        (appointment_draft or {}).get("reason"),
        ai_result.get("reason"),
        ai_result.get("urgency"),
    )
    # Keep key normalized as "location" across extractor + bot checks.
    location = _first_non_empty(
        (appointment_draft or {}).get("location"),
        ai_result.get("location"),
        ai_result.get("location_name"),
    )

    # 2. Direct the request to the AppointmentOrchestrator for robust booking
    booking_result = orchestrator.handle_booking_request(
        patient_id=request_data["id"],
        name=name,
        doctor_id=101,  # Default doctor ID for clinic
        preferred_time=preferred_time_for_booking
    )

    appt = {
        "patient_id": request_data["id"],
        "name": name,
        "preferred_time": preferred_time,
        "reason": reason,
        "location": location,
        "urgency": ai_result.get("urgency"),
        "source": source,
        "extracted": (appointment_draft or {}).get("extracted", {}),
        "generic": (appointment_draft or {}).get("generic", {}),
        "ai_result": ai_result,
        "booking_status": booking_result.get("message"),
        "booking_success": bool(booking_result.get("success")),
        "booked_slot": booking_result.get("slot"),
        "booking_feedback": _build_booking_feedback(booking_result),
    }

    return appt


@app.route("/")
def chat_page():
    """
    Simple web UI that simulates a WhatsApp-style chat with the intake bot.
    """
    return render_template("chat.html")


@app.route("/call-simulation")
def call_simulation_page():
    """Phone call simulation UI."""
    return render_template("call_simulation.html")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        return "WhatsApp Webhook Running"

    data = request.json or {}

    sender = data.get("from")
    name = data.get("name")
    text = data.get("text")
    timestamp = data.get("timestamp")

    message_type = data.get("type", "text")  # 'text' or 'voice' (voice note)

    print("\nIncoming WhatsApp Message")
    print("Sender:", sender)
    print("Name:", name)
    print("Type:", message_type)
    print("Text:", text)

    if message_type == "text" and _is_cancel_intent(text):
        cancel_result = _cancel_latest_booking(sender)
        result = {
            "sender": sender,
            "name": name,
            "timestamp": timestamp,
            "original_message": text,
            "extracted_information": {},
            "appointment": {
                "source": "whatsapp_text_cancel",
                "booking_success": cancel_result.get("success"),
                "booking_feedback": cancel_result.get("message"),
                "booked_slot": cancel_result.get("slot"),
            },
            "booking_success": cancel_result.get("success"),
            "booking_feedback": cancel_result.get("message"),
            "missing_fields": [],
            "reply_message": None,
        }
        print("\nProcessed JSON:")
        print(result)
        return jsonify(result)

    session_key = f"chat::{sender or 'unknown'}"

    # Build appointment depending on whether this is a text message
    # or a simulated voice note (already transcribed text).
    message_text = text or ""
    appointment_source = "whatsapp_text"
    if message_type == "voice":
        # For this demo, we assume `text` already contains the transcript.
        transcript = transcribe_voice(text or "")
        message_text = transcript or ""
        appointment_source = "whatsapp_voice"
    else:
        appointment_source = "whatsapp_text"

    incoming_draft = _parse_appointment_from_text(
        text=message_text,
        source=appointment_source,
        fallback_name=name,
    )
    existing_session = INTAKE_SESSIONS.get(session_key)
    merged_draft = _merge_appointment_drafts(existing_session, incoming_draft)
    missing_fields = _validate_required_fields(merged_draft)

    if missing_fields:
        INTAKE_SESSIONS[session_key] = merged_draft
        reply_message = _build_missing_info_prompt(missing_fields)
        result = {
            "sender": sender,
            "name": name,
            "timestamp": timestamp,
            "original_message": text,
            "extracted_information": merged_draft.get("generic", {}),
            "appointment": merged_draft,
            "booking_success": None,
            "booking_feedback": None,
            "missing_fields": missing_fields,
            "reply_message": reply_message,
        }
        print("\nProcessed JSON:")
        print(result)
        return jsonify(result)

    appointment = _store_appointment_from_structured(merged_draft)
    INTAKE_SESSIONS.pop(session_key, None)

    _register_booking(
        sender=sender,
        incoming_name=name,
        source=appointment_source,
        raw_text=message_text,
        appointment=appointment,
    )

    # Normalize extractor output for frontend and follow-up checks.
    extracted_generic = appointment.get("generic") or extract_data(message_text)
    if not isinstance(extracted_generic, dict):
        extracted_generic = {"location": None, "preferred_slot": None, "symptoms": []}

    reply_message = None
    missing_fields = []

    result = {
        "sender": sender,
        "name": name,
        "timestamp": timestamp,
        "original_message": text,
        "extracted_information": extracted_generic,
        "appointment": appointment,
        "booking_success": appointment.get("booking_success"),
        "booking_feedback": appointment.get("booking_feedback"),
        "missing_fields": missing_fields,
        "reply_message": reply_message,
    }

    print("\nProcessed JSON:")
    print(result)

    return jsonify(result)


@app.route("/voice_call_webhook", methods=["POST"])
def voice_call_webhook():
    """
    Simulated webhook for a voice call provider.
    Expects JSON like:
    {
        "caller_id": "+919876543210",
        "transcript": "Hello, this is Ravi. I want to see a cardiologist tomorrow morning for chest pain."
    }
    """
    data = request.json or {}
    caller_id = data.get("caller_id")
    raw_transcript = data.get("transcript", "")

    print("\nIncoming Voice Call")
    print("Caller ID:", caller_id)
    print("Transcript:", raw_transcript)

    transcript = transcribe_voice(raw_transcript)
    session_key = f"voice::{caller_id or 'unknown'}"
    incoming_draft = _parse_appointment_from_text(
        text=transcript,
        source="voice_call",
        fallback_name=None,
    )
    merged_draft = _merge_appointment_drafts(INTAKE_SESSIONS.get(session_key), incoming_draft)
    missing_fields = _validate_required_fields(merged_draft)

    if missing_fields:
        INTAKE_SESSIONS[session_key] = merged_draft
        response = {
            "caller_id": caller_id,
            "transcript": transcript,
            "extractor_output": merged_draft,
            "missing_fields": missing_fields,
            "ai_response": _build_missing_info_prompt(missing_fields),
            "booking_success": None,
            "booking_feedback": None,
        }
        print("\nVoice Call Processed JSON:")
        print(response)
        return jsonify(response)

    appointment = _store_appointment_from_structured(merged_draft)
    INTAKE_SESSIONS.pop(session_key, None)

    response = {
        "caller_id": caller_id,
        "transcript": transcript,
        "appointment": appointment,
        "booking_success": appointment.get("booking_success"),
        "booking_feedback": appointment.get("booking_feedback"),
    }

    print("\nVoice Call Processed JSON:")
    print(response)

    return jsonify(response)


@app.route("/api/call/process", methods=["POST"])
def process_call_pipeline():
    """
    End-to-end pipeline for call simulation:
    transcript -> extractor/orchestrator -> slot result -> response text.
    """
    data = request.json or {}
    caller_id = data.get("caller_id", "unknown")
    raw_transcript = data.get("transcript", "")

    transcript = transcribe_voice(raw_transcript)
    session_key = f"call-ui::{caller_id or 'unknown'}"
    incoming_draft = _parse_appointment_from_text(
        text=transcript,
        source="voice",
        fallback_name=None,
    )
    merged_draft = _merge_appointment_drafts(INTAKE_SESSIONS.get(session_key), incoming_draft)
    missing_fields = _validate_required_fields(merged_draft)

    if missing_fields:
        INTAKE_SESSIONS[session_key] = merged_draft
        ai_response = _build_missing_info_prompt(missing_fields)
        result = {
            "caller_id": caller_id,
            "transcript": transcript,
            "appointment": merged_draft,
            "extractor_output": merged_draft,
            "slot_result": {"status": "pending"},
            "ai_response": ai_response,
            "booking_success": None,
            "booking_feedback": None,
            "missing_fields": missing_fields,
        }
        print("\nCall Simulation Processed JSON:")
        print(result)
        return jsonify(result)

    appointment = _store_appointment_from_structured(merged_draft)
    INTAKE_SESSIONS.pop(session_key, None)
    slot_result = _build_slot_allocation_result(appointment)
    ai_response = _build_call_response_text(slot_result)

    result = {
        "caller_id": caller_id,
        "transcript": transcript,
        "appointment": appointment,
        "extractor_output": appointment.get("extracted", {}),
        "slot_result": slot_result,
        "ai_response": ai_response,
        "booking_success": appointment.get("booking_success"),
        "booking_feedback": appointment.get("booking_feedback"),
        "missing_fields": [],
    }

    print("\nCall Simulation Processed JSON:")
    print(result)
    return jsonify(result)


@app.route("/reset_demo_state", methods=["POST", "GET"])
def reset_demo_state():
    """Reset calendar/waitlist mock files so booking demos can run repeatedly."""
    reset_result = reset_system_state()
    _save_booking_registry([])
    INTAKE_SESSIONS.clear()
    reset_result["cleared_booking_registry"] = str(BOOKING_REGISTRY_PATH)
    reset_result["cleared_intake_sessions"] = True
    return jsonify(reset_result)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
