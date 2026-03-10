import speech_recognition as sr
import spacy
import re
from datetime import datetime, timedelta

# Load spaCy model
nlp = spacy.load('en_core_web_sm')

def voice_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Please speak...")
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio)
        print("Transcribed Text:", text)
        return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return ""
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return ""

def extract_features(text):
    text_lower = text.lower()
    doc = nlp(text)

    # Name extraction (spaCy NER + regex fallback)
    name = None
    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            name = ent.text.title()
            break
    if not name:
        m = re.search(r"(?:this is|i am|i'm|my name is)\s+([a-zA-Z]+)", text_lower)
        if m:
            name = m.group(1).title()
        else:
            m = re.search(r"name[:\-]\s*([a-zA-Z]+)", text_lower)
            if m:
                name = m.group(1).title()

    # Symptoms extraction
    symptoms_keywords = [
        "fever","cough","cold","vomiting","dizziness",
        "headache","body ache","chest pain","sore throat","nauseous"
    ]
    symptoms = [s for s in symptoms_keywords if s in text_lower]

    # Location extraction
    location = None
    location_patterns = [
        r"in\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)",
        r"from\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)",
        r"near\s+([a-zA-Z ]+?)(?:\s+and|\s+have|\s+need|\.|,|$)"
    ]
    for pattern in location_patterns:
        match = re.search(pattern, text_lower)
        if match:
            location = match.group(1).strip().title()
            break

    # Preferred time extraction
    preferred_time = None
    if "tomorrow" in text_lower:
        base = datetime.utcnow() + timedelta(days=1)
        hour = 9 if "morning" in text_lower else 15 if "afternoon" in text_lower else 18 if "evening" in text_lower else 10
        preferred_time = base.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()

    # Reason extraction
    reason = ", ".join(symptoms) if symptoms else text

    return {
        "name": name,
        "symptoms": symptoms,
        "location": location,
        "preferred_time": preferred_time,
        "reason": reason,
        "source": "voice"
    }

if __name__ == "__main__":
    # Step 1: Get text from voice
    text = voice_to_text()
    # Step 2: Extract features
    features = extract_features(text)
    print("Extracted Features:")
    print(features)
