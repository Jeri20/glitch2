
import re

def extract_data(text):

    text_lower = text.lower()

    # Detect time slot
    slot = None
    if "morning" in text_lower:
        slot = "morning"
    elif "afternoon" in text_lower:
        slot = "afternoon"
    elif "evening" in text_lower:
        slot = "evening"

    # Detect location
    location_patterns = [
    r"in\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)",
    r"from\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)",
    r"near\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)"
]

    location = None
    for pattern in location_patterns:
        match = re.search(pattern, text_lower)
        if match:
            location = match.group(1).strip().title()
            break

    # Detect symptoms
    symptoms_keywords = [
        "fever","cough","cold","vomiting","dizziness",
        "headache","body ache","chest pain","sore throat"
    ]

    symptoms = [s for s in symptoms_keywords if s in text_lower]

    return {
        "location": location,
        "preferred_slot": slot,
        "symptoms": symptoms
    }


from datetime import datetime, timedelta


def _extract_name(text_lower):
    """
    Try to pull the person's name from patterns like:
    - 'Hello, this is Ravi'
    - 'Hi I'm Ravi'
    - 'I am Ravi'
    - 'Name: Ravi'
    """
    import spacy
    nlp = spacy.load('en_core_web_sm')
    # Use spaCy NER to extract PERSON entities
    doc = nlp(text_lower)
    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            return ent.text.title()

    # Fallback to regex if spaCy fails
    m = re.search(r"(?:this is|i am|i'm|my name is)\s+([a-zA-Z]+)", text_lower)
    if m:
        return m.group(1).title()

    m = re.search(r"name[:\-]\s*([a-zA-Z]+)", text_lower)
    if m:
        return m.group(1).title()

    m = re.search(r"hello[,\s]+([a-zA-Z]+)", text_lower)
    if m:
        return m.group(1).title()

    return None
    m = re.search(r"(this is|i am|i'm)\s+([a-zA-Z]+)", text_lower)
    if m:
        return m.group(2).title()

    m = re.search(r"name[:\-]\s*([a-zA-Z]+)", text_lower)
    if m:
        return m.group(1).title()

    return None


def _extract_preferred_time(text_lower):
    """
    Convert phrases like 'tomorrow morning' or 'tomorrow 10am'
    to an ISO8601 datetime string.
    """
    if "tomorrow" not in text_lower:
        return None

    base = datetime.utcnow() + timedelta(days=1)
    hour = 10
    minute = 0

    if "10am" in text_lower or "10 am" in text_lower:
        hour = 10
    elif "9am" in text_lower or "9 am" in text_lower:
        hour = 9
    elif "morning" in text_lower:
        hour = 9
    elif "afternoon" in text_lower:
        hour = 15
    elif "evening" in text_lower:
        hour = 18

    preferred_dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return preferred_dt.isoformat()


def _extract_reason(text, text_lower):
    """
    Use symptom list as the reason if we find any,
    otherwise fall back to the whole text or a 'Reason:' segment.
    """
    base = extract_data(text)
    if base["symptoms"]:
        return ", ".join(base["symptoms"])

    m = re.search(r"reason[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return text


def extract_appointment(text, source):
    """
    Build a structured appointment JSON from free text.

    Example output:
    {
        "name": "Ravi",
        "preferred_time": "2026-03-10T10:00:00",
        "reason": "chest pain",
        "source": "voice"
    }
    """
    text_lower = text.lower()

    name = _extract_name(text_lower)
    preferred_time = _extract_preferred_time(text_lower)
    reason = _extract_reason(text, text_lower)

    # Reuse generic extractor to also capture location
    generic = extract_data(text)
    location = generic.get("location")

    return {
        "name": name,
        "preferred_time": preferred_time,
        "reason": reason,
        "location": location,
        "source": source,
    }