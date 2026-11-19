"""CAIFE six-intent baseline. Run from the repository root."""
import argparse
import hashlib
import json
from collections import Counter
from importlib.metadata import version
from itertools import combinations
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


def read_splits(directory):
    splits, hashes = {}, {}
    for name in ("train", "validation", "test"):
        raw = (directory / f"{name}.jsonl").read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
        if not rows or any(r["split"] != name or not r["text"].strip() for r in rows):
            raise ValueError(f"Empty or invalid partition: {name}")
        splits[name] = rows
    for left, right in combinations(splits, 2):
        for key in ("group_id", "id", "text"):
            if {r[key] for r in splits[left]} & {r[key] for r in splits[right]}:
                raise ValueError(f"Split overlap: {left}/{right}, {key}")
    return splits, hashes


def scores(actual, predicted):
    return {"accuracy": float(accuracy_score(actual, predicted)),
            "macro_f1": float(f1_score(actual, predicted, average="macro", zero_division=0))}


def train(directory, out):
    splits, hashes = read_splits(directory)
    x = {s: [r["text"] for r in rows] for s, rows in splits.items()}
    y = {s: [r["intent"] for r in rows] for s, rows in splits.items()}
    labels = sorted(set(y["train"]))
    if any(set(values) != set(labels) for values in y.values()):
        raise ValueError("Partitions must cover the same intents")
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), lowercase=False, dtype=np.float32)
    train_x = vectorizer.fit_transform(x["train"])
    valid_x = vectorizer.transform(x["validation"])
    # Fixed settings. Exact validation ties select logistic regression by insertion order.
    candidates = {
        "LogisticRegression": LogisticRegression(C=1, solver="lbfgs", max_iter=2000, random_state=42),
        "LinearSVC": LinearSVC(C=1, dual="auto", max_iter=5000, random_state=42),
    }
    validation = {}
    for name, model in candidates.items():
        model.fit(train_x, y["train"])
        validation[name] = scores(y["validation"], model.predict(valid_x))
    winner = max(validation, key=lambda n: validation[n]["macro_f1"])
    pipeline = Pipeline([("tfidf", vectorizer), ("classifier", candidates[winner])])
    pred = pipeline.predict(x["test"])
    counts = {s: dict(Counter(values)) for s, values in y.items()}
    metrics = {
        "labels": labels, "split_counts": counts, "input_sha256": hashes,
        "group_counts": {s: len({r["group_id"] for r in rows}) for s, rows in splits.items()},
        "versions": {p: version(p) for p in ["scikit-learn", "numpy", "scipy", "joblib"]},
        "features": train_x.shape[1], "validation": validation, "selected": winner,
        "test": scores(y["test"], pred),
        "correct": int(np.sum(pred == np.array(y["test"]))),
        "classification": classification_report(y["test"], pred, labels=labels, output_dict=True, zero_division=0),
        "confusion": confusion_matrix(y["test"], pred, labels=labels).tolist(),
        "errors": [{"text": r["text"], "group_id": r["group_id"], "id": r["id"],
                    "actual": r["intent"], "predicted": str(p)}
                   for r, p in zip(splits["test"], pred) if r["intent"] != p],
    }
    out.mkdir(exist_ok=True, parents=True)
    joblib.dump(pipeline, out / "intent_pipeline.joblib", compress=3)
    restored = joblib.load(out / "intent_pipeline.joblib")
    if not np.array_equal(pred, restored.predict(x["test"])):
        raise RuntimeError("Reloaded pipeline changed predictions")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("selected", "validation", "test", "correct", "features")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/intents/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/intent_baseline"))
    args = parser.parse_args()
    train(args.input_dir, args.output_dir)
