"""Diagnostic examples written separately after seeing the baseline test score."""
import json
from pathlib import Path

import joblib

CASES = [
    ("주문_추가", "아아 둘이요"),
    ("주문_추가", "바닐라라테 하나 부탁해요"),
    ("주문_삭제", "방금 담은 거 빼 줘"),
    ("주문_삭제", "크루아상은 안 살래요"),
    ("수량_변경", "그거 세 개 말고 두 개로"),
    ("수량_변경", "라테가 하나 더 필요해요. 총 두 잔으로요"),
    ("메뉴_문의", "이거 디카페인도 돼요?"),
    ("메뉴_문의", "우유 안 든 거 뭐 있어요?"),
    ("화면_조작", "글씨가 작아. 키워 줘"),
    ("화면_조작", "커피 종류만 띄워 줘"),
    ("주문_확인", "내가 뭘 시켰더라?"),
    ("주문_확인", "지금까지 담은 거 읽어 봐요"),
]


if __name__ == "__main__":
    folder = Path("models/intent_baseline")
    pipeline = joblib.load(folder / "intent_pipeline.joblib")
    inputs = [text for _, text in CASES]
    root = Path("data/intents/processed")
    known = {json.loads(line)["text"] for split in ("train", "validation", "test")
             for line in (root / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line}
    if known.intersection(inputs):
        raise ValueError("Probe overlaps baseline")
    predicted = pipeline.predict(inputs)
    rows = [{"text": text, "expected": label, "predicted": str(p)}
            for (label, text), p in zip(CASES, predicted)]
    (folder / "diagnostics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(sum(r["expected"] == r["predicted"] for r in rows), "/", len(rows))
