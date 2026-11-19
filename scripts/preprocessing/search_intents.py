"""Build and verify CAIFE's offline order-intent example search database."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unicodedata

import joblib
import numpy as np
import sqlite_vec

from probe_intents import CASES
from train_intents import read_splits


def connect(path, readonly=False):
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) if readonly else sqlite3.connect(path)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.row_factory = sqlite3.Row
        return db
    except Exception:
        db.close()
        raise


def search(db, vectorizer, phrase, limit=3):
    text = " ".join(unicodedata.normalize("NFC", phrase).split())
    query = vectorizer.transform([text])
    if not query.nnz:
        return []
    vector = query.toarray()[0].astype(np.float32).tobytes()
    rows = db.execute("""
        SELECT e.id, e.phrase, e.intent, vec_distance_cosine(v.embedding, ?) AS cosine_gap
        FROM example_vectors v JOIN examples e ON e.rowid = v.rowid
        WHERE cosine_gap < 1 ORDER BY cosine_gap, e.id LIMIT ?
    """, (vector, limit))
    return [dict(id=r["id"], phrase=r["phrase"], intent=r["intent"],
                 similarity=round(1 - r["cosine_gap"], 5)) for r in rows]


def evaluate(db, vectorizer, examples):
    hits1 = hits3 = empty = 0
    cases = []
    for phrase, expected in examples:
        near = search(db, vectorizer, phrase)
        hits1 += bool(near and near[0]["intent"] == expected)
        hits3 += any(r["intent"] == expected for r in near)
        empty += not near
        cases.append({"phrase": phrase, "expected": expected, "matches": near})
    return {"n": len(cases), "hit1": hits1, "hit3": hits3, "empty": empty}, cases


def build(input_dir, model_dir, out_dir):
    splits, hashes = read_splits(input_dir)
    metrics = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
    if hashes != metrics["input_sha256"]:
        raise ValueError("Dataset differs from the classifier training snapshot")
    trained = model_dir / "intent_pipeline.joblib"
    model_hash = hashlib.sha256(trained.read_bytes()).hexdigest()
    pipeline = joblib.load(trained)
    vectorizer = pipeline.named_steps["tfidf"]
    rows = splits["train"]
    matrix = vectorizer.transform([r["text"] for r in rows])
    if np.any(matrix.getnnz(axis=1) == 0):
        raise ValueError("Empty training vector")
    if {t for _, t in CASES} & {r["text"] for part in splits.values() for r in part}:
        raise ValueError("Probe overlaps training or evaluation data")
    out_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out_dir) as temp:
        db_file = Path(temp).resolve() / "intent_vectors.sqlite3"
        with closing(connect(db_file)) as db, db:
            db.execute("CREATE TABLE examples(id TEXT UNIQUE NOT NULL, phrase TEXT UNIQUE NOT NULL, intent TEXT NOT NULL, group_id TEXT NOT NULL, source TEXT NOT NULL)")
            db.execute(f"CREATE VIRTUAL TABLE example_vectors USING vec0(embedding float[{matrix.shape[1]}] distance_metric=cosine)")
            db.execute("CREATE TABLE metadata(model_sha256 TEXT NOT NULL, train_sha256 TEXT NOT NULL)")
            db.execute("INSERT INTO metadata VALUES (?,?)", (model_hash, hashes["train"]))
            for r, vec in zip(rows, matrix):
                insert = db.execute("INSERT INTO examples VALUES (?,?,?,?,?)",
                                    (r["id"], r["text"], r["intent"], r["group_id"], r["source"]))
                db.execute("INSERT INTO example_vectors(rowid, embedding) VALUES (?,?)",
                           (insert.lastrowid, vec.toarray()[0].tobytes()))
        with closing(connect(db_file, readonly=True)) as db:
            counts = db.execute("SELECT count(*) FROM examples e JOIN example_vectors v ON e.rowid=v.rowid").fetchone()[0]
            if counts != len(rows) or db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Incomplete vector database")
            same = search(db, vectorizer, rows[0]["text"])
            if not same or same[0]["id"] != rows[0]["id"] or same[0]["similarity"] < 0.99999:
                raise ValueError("Exact-match retrieval failed")
            report = dict(engine=db.execute("SELECT vec_version()").fetchone()[0],
                          rows=counts, dimensions=matrix.shape[1], model_sha256=model_hash, input_sha256=hashes,
                          labels=dict(Counter(r["intent"] for r in rows)), results={})
            for name in ("validation", "test", "probe"):
                examples = ([(text, intent) for intent, text in CASES] if name == "probe"
                            else [(r["text"], r["intent"]) for r in splits[name]])
                scores, cases = evaluate(db, vectorizer, examples)
                report["results"][name] = scores
                if name == "probe":
                    report["probe_cases"] = cases
            if search(db, vectorizer, "🛸"):
                raise ValueError("Unknown query should have no result")
        report_file = Path(temp) / "retrieval_metrics.json"
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        db_file.replace(out_dir / db_file.name)
        report_file.replace(out_dir / report_file.name)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/intents/processed"))
    parser.add_argument("--model-dir", type=Path, default=Path("models/intent_baseline"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/intent_search"))
    parser.add_argument("--query", help="Search a previously built database")
    args = parser.parse_args()
    if args.query is None:
        result = build(args.input_dir, args.model_dir, args.output_dir)
        print(json.dumps(result["results"], indent=2))
    else:
        trained = args.model_dir / "intent_pipeline.joblib"
        with closing(connect((args.output_dir / "intent_vectors.sqlite3").resolve(), readonly=True)) as db:
            expected = db.execute("SELECT model_sha256 FROM metadata").fetchone()[0]
            if expected != hashlib.sha256(trained.read_bytes()).hexdigest():
                raise ValueError("Rebuild the database for this model")
            vectorizer = joblib.load(trained).named_steps["tfidf"]
            print(json.dumps(search(db, vectorizer, args.query), ensure_ascii=False, indent=2))
