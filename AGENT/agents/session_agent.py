"""Session context agent."""


class SessionAgent:
    """Tracks user sessions, history, hospitals, and appointment attempts by user id."""

    def __init__(self) -> None:
        # Example:
        # sessions = {
        #   1: {
        #       "hospital": "Apollo Velachery",
        #       "last_request": {...},
        #       "history": [...],
        #       "appointment_attempts": [...]
        #   }
        # }
        self.sessions: dict = {}

    def _normalize_user_id(self, user_id):
        if user_id is None:
            return "Unknown"
        return user_id

    def _ensure_session(self, user_id):
        key = self._normalize_user_id(user_id)
        if key in self.sessions:
            return self.sessions[key]

        session = {
            "hospital": None,
            "last_request": None,
            "history": [],
            "appointment_attempts": [],
        }
        self.sessions[key] = session
        return session

    def get_user_history(self, user_id):
        """Return request history list for a user id."""
        key = self._normalize_user_id(user_id)
        session = self.sessions.get(key)
        if not session:
            return []
        return list(session.get("history", []))

    def store_assigned_hospital(self, user_id, hospital):
        """Persist assigned hospital for a user id."""
        session = self._ensure_session(user_id)
        session["hospital"] = hospital
        return hospital

    def update_request(self, user_id, request):
        """Update user session with latest request and appointment attempt."""
        session = self._ensure_session(user_id)
        session["last_request"] = request
        session.setdefault("history", []).append(request)
        session.setdefault("appointment_attempts", []).append(request)
        return session

    # Backward-compatible helpers used elsewhere in the codebase
    def create_or_update_session(self, name: str, request: dict) -> dict:
        return self.update_request(name, request)

    def get_session(self, name):
        key = self._normalize_user_id(name)
        return self.sessions.get(key)

    def set_memory_value(self, name, key: str, value):
        if key == "assigned_hospital":
            return self.store_assigned_hospital(name, value)

        session = self._ensure_session(name)
        session[key] = value
        return value

    def get_memory_value(self, name, key: str, default=None):
        session = self.get_session(name)
        if not session:
            return default

        if key == "assigned_hospital":
            return session.get("hospital", default)

        return session.get(key, default)

    def update(self, key, value: dict) -> dict:
        return self.update_request(key, value)
