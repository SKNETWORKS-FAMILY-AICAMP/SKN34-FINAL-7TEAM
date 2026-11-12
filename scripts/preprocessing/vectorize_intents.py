from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import scipy
import sklearn
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

HERE = Path(__file__).resolve().parent
INPUT = HERE / "output"
OUT = INPUT


def read_split(split: str) -> list[dict]:
    with (INPUT / f"{split}.jsonl").open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows or any(row["split"] != split or not row["text"] for row in rows):
        raise ValueError(f"invalid or empty split: {split}")
    return rows


def main() -> None:
    global INPUT, OUT
    parser = argparse.ArgumentParser(description="Fit TF-IDF on train and transform all splits")
    parser.add_argument("--input-dir", type=Path, default=INPUT, help="Directory containing train/validation/test JSONL and manifest")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory, defaults to input directory")
    args = parser.parse_args()
    INPUT = args.input_dir.resolve()
    OUT = args.output_dir.resolve() if args.output_dir else INPUT
    OUT.mkdir(parents=True, exist_ok=True)
    data = {s: read_split(s) for s in ("train", "validation", "test")}
    # Labelled examples and groups must not overlap between any split.
    for index, left in enumerate(data):
        for right in list(data)[index + 1:]:
            assert not ({r["group_id"] for r in data[left]} & {r["group_id"] for r in data[right]})
            assert not ({r["text"] for r in data[left]} & {r["text"] for r in data[right]})

    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3),
                                 dtype=np.float32, lowercase=False)
    matrices = {"train": vectorizer.fit_transform([r["text"] for r in data["train"]])}
    for split in ("validation", "test"):
        matrices[split] = vectorizer.transform([r["text"] for r in data[split]])

    for split, matrix in matrices.items():
        if matrix.shape[0] != len(data[split]) or matrix.shape[1] != len(vectorizer.vocabulary_):
            raise ValueError(f"matrix shape mismatch: {split}")
        save_npz(OUT / f"tfidf_{split}.npz", matrix)
    joblib.dump(vectorizer, OUT / "tfidf_vectorizer.joblib")
    restored = joblib.load(OUT / "tfidf_vectorizer.joblib")
    probe = [data["test"][0]["text"]]
    if (restored.transform(probe) != vectorizer.transform(probe)).nnz != 0:
        raise ValueError("saved vectorizer and loaded vectorizer disagree")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads((INPUT / "manifest.json").read_text(encoding="utf-8"))
    manifest["tfidf"] = {
        "analyzer": "char",
        "ngram_range": [2, 3],
        "fit_partition": "train",
        "transformed_partitions": ["train", "validation", "test"],
        "training_documents": len(data["train"]),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "matrices": {s: {"shape": list(m.shape), "nonzero": int(m.nnz),
                         "zero_rows": int(np.count_nonzero(m.getnnz(axis=1) == 0))}
                     for s, m in matrices.items()},
        "dtype": "float32",
        "label_alignment": "tfidf_{split}.npz rows follow the same order as input-dir/{split}.jsonl",
        "vectorizer_file": "tfidf_vectorizer.joblib",
        "versions": {"scikit-learn": sklearn.__version__, "numpy": np.__version__,
                     "scipy": scipy.__version__, "joblib": joblib.__version__},
    }
    manifest["training_status"] = "TF-IDF 변환기만 학습 데이터에 맞춤. 주문 의도 분류 모델 학습은 수행하지 않음"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["tfidf"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

