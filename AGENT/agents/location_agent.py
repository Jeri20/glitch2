"""Location extraction agent using spaCy NER and geopy."""

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
import spacy


nlp = spacy.load("en_core_web_sm")


class LocationAgent:
    """Extracts location text (GPE) and resolves it to coordinates."""

    def __init__(self, spacy_model: str = "en_core_web_sm", user_agent: str = "appointment-ai") -> None:
        try:
            self.nlp = spacy.load(spacy_model)
        except OSError as err:
            raise RuntimeError(
                "spaCy model not found. Install it with: python -m spacy download en_core_web_sm"
            ) from err

        self.geolocator = Nominatim(user_agent=user_agent)

    def extract(self, raw_text: str) -> dict:
        """Return location name and coordinates from free text."""
        text = str(raw_text or "").strip()
        if not text:
            return {
                "location_name": None,
                "location": None,
                "latitude": None,
                "longitude": None,
            }

        doc = self.nlp(text)
        gpe_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "GPE" and ent.text.strip()]

        if not gpe_entities:
            return {
                "location_name": None,
                "location": None,
                "latitude": None,
                "longitude": None,
            }

        location_name = gpe_entities[0]

        latitude = None
        longitude = None
        try:
            geocoded = self.geolocator.geocode(location_name, exactly_one=True, timeout=10)
            if geocoded is not None:
                latitude = float(geocoded.latitude)
                longitude = float(geocoded.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            pass

        return {
            "location_name": location_name,
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
        }
