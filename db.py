import json
import os
from datetime import datetime

JSON_PATH = "appointments.json"


def _load_all():
    """
    Load the full JSON list of appointments from disk.
    Returns a Python list; if file doesn't exist, returns [].
    """
    if not os.path.exists(JSON_PATH):
        return []

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # If file is corrupt/empty, start fresh
            return []

    # Ensure it's always a list
    if isinstance(data, list):
        return data
    return []


def _save_all(records):
    """
    Overwrite the JSON file with the given list of appointment records.
    """
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def init_db():
    """
    For JSON storage, 'init' just ensures the file exists with an empty list.
    """
    if not os.path.exists(JSON_PATH):
        _save_all([])


def save_appointment(name, preferred_time, reason, location, source, raw_text):
    """
    Append a new appointment object to the JSON file.
    """
    records = _load_all()

    new_record = {
        "id": len(records) + 1,
        "name": name,
        "preferred_time": preferred_time,
        "reason": reason,
        "location": location,
        "source": source,
        "raw_text": raw_text,
        "created_at": datetime.utcnow().isoformat(),
    }

    records.append(new_record)
    _save_all(records)
