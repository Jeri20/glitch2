"""Train a DistilBERT urgency classifier from urgency_dataset.csv."""

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import Dataset
from sklearn.model_selection import train_test_split
from transformers import (
    AutoTokenizer,
    DistilBertForSequenceClassification,
    Trainer,
    TrainingArguments,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "urgency_dataset.csv"
MODEL_NAME = "distilbert-base-uncased"
MODEL_DIR = PROJECT_ROOT / "models" / "bert_urgency_model"
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"

LABEL_MAP = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}
ID2LABEL = {value: key for key, value in LABEL_MAP.items()}


def _load_and_prepare_dataframe(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = {"reason", "urgency"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["reason"] = df["reason"].fillna("").astype(str)
    df["urgency"] = df["urgency"].astype(str).str.strip().str.upper()

    unknown_labels = sorted(set(df["urgency"]) - set(LABEL_MAP))
    if unknown_labels:
        raise ValueError(f"Unknown urgency labels found: {unknown_labels}")

    # 1) Map urgency labels: LOW=0, MEDIUM=1, HIGH=2
    df["label"] = df["urgency"].map(LABEL_MAP).astype(int)

    return df[["reason", "label"]]


def _build_datasets(df: pd.DataFrame, tokenizer: AutoTokenizer) -> tuple[Dataset, Dataset]:
    train_df, eval_df = train_test_split(
        df,
        test_size=0.2,
        random_state=42,
        stratify=df["label"],
    )

    train_ds = Dataset.from_pandas(train_df.reset_index(drop=True))
    eval_ds = Dataset.from_pandas(eval_df.reset_index(drop=True))

    # 3) Tokenize reason column
    def tokenize(batch: dict) -> dict:
        return tokenizer(batch["reason"], truncation=True, padding="max_length", max_length=128)

    train_ds = train_ds.map(tokenize, batched=True)
    eval_ds = eval_ds.map(tokenize, batched=True)

    columns = ["input_ids", "attention_mask", "label"]
    train_ds.set_format(type="torch", columns=columns)
    eval_ds.set_format(type="torch", columns=columns)

    return train_ds, eval_ds


def _compute_metrics(eval_pred: tuple[np.ndarray, np.ndarray]) -> dict:
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = (predictions == labels).mean().item()
    return {"accuracy": accuracy}


def _make_training_arguments() -> TrainingArguments:
    common = {
        "output_dir": str(CHECKPOINT_DIR),
        "num_train_epochs": 3,
        "per_device_train_batch_size": 16,
        "per_device_eval_batch_size": 16,
        "save_strategy": "epoch",
        "logging_strategy": "epoch",
        "report_to": "none",
        "seed": 42,
    }

    # transformers changed this field name from `evaluation_strategy` to `eval_strategy`
    # in newer releases; keep compatibility with both.
    try:
        return TrainingArguments(**common, eval_strategy="epoch")
    except TypeError:
        return TrainingArguments(**common, evaluation_strategy="epoch")


def train() -> None:
    df = _load_and_prepare_dataframe(DATA_PATH)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_dataset, eval_dataset = _build_datasets(df, tokenizer)

    # 4) Fine tune DistilBertForSequenceClassification
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL_MAP,
    )

    # 5) Train for 3 epochs
    training_args = _make_training_arguments()

    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_dataset,
        "eval_dataset": eval_dataset,
        "compute_metrics": _compute_metrics,
    }
    trainer_params = set(inspect.signature(Trainer.__init__).parameters)
    if "processing_class" in trainer_params:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_params:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = Trainer(**trainer_kwargs)

    trainer.train()
    metrics = trainer.evaluate()
    print(f"Validation accuracy: {metrics.get('eval_accuracy', 0.0):.4f}")

    # 6) Save model and tokenizer to models/bert_urgency_model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MODEL_DIR)
    tokenizer.save_pretrained(MODEL_DIR)
    print(f"Model and tokenizer saved to: {MODEL_DIR}")


if __name__ == "__main__":
    train()
