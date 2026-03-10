"""Urgency classification agent backed by a fine-tuned DistilBERT model."""

from pathlib import Path

import torch
from transformers import AutoTokenizer, DistilBertForSequenceClassification


class UrgencyAgent:
    """Loads a BERT urgency model and predicts LOW/MEDIUM/HIGH labels."""

    def __init__(self, model_dir: Path | None = None, device: str | None = None) -> None:
        default_model_dir = Path(__file__).resolve().parents[1] / "models" / "bert_urgency_model"
        self.model_dir = Path(model_dir) if model_dir is not None else default_model_dir

        self.model = None
        self.tokenizer = None
        if not self.model_dir.exists() or not (self.model_dir / "config.json").exists():
            print(f"Warning: Model directory not found or empty: {self.model_dir}. Using simulated urgency fallback.")
            return

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
            self.model = DistilBertForSequenceClassification.from_pretrained(self.model_dir)

            if device is not None:
                self.device = torch.device(device)
            else:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            print(f"Warning: Failed to load model ({e}). Using simulated urgency fallback.")
            self.model = None

    def classify(self, reason: str) -> str:
        """Tokenize input text, run inference, and return urgency label."""
        if self.model is None or self.tokenizer is None:
            reason_lower = str(reason).lower()
            if any(w in reason_lower for w in ["pain", "severe", "emergency", "urgent", "chest"]): return "HIGH"
            if any(w in reason_lower for w in ["fever", "cough", "sick"]): return "MEDIUM"
            return "LOW"
        
        encoded = self.tokenizer(
            reason,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128,
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = self.model(**encoded).logits
            pred_id = int(torch.argmax(logits, dim=-1).item())

        id2label = self.model.config.id2label or {}
        label = id2label.get(pred_id, id2label.get(str(pred_id), "LOW"))
        label = str(label).upper()

        if label not in {"LOW", "MEDIUM", "HIGH"}:
            fallback = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
            label = fallback.get(pred_id, "LOW")

        return label

    def classify_urgency(self, reason: str) -> str:
        """Tool-friendly alias for urgency classification."""
        return self.classify(reason)

    def predict(self, request: dict) -> str:
        """Backward-compatible wrapper that classifies request reason text."""
        reason = str(request.get("reason", ""))
        return self.classify(reason)
