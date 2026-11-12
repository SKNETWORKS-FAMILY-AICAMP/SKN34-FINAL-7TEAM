from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

# 모든 문장은 시연을 위해 직접 작성한 합성 문장이다. 녹음 또는 STT 결과가 아니다.
SEED = 42
HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
ENDINGS = ("줘", "주세요", "주시겠어요")

# 각 문장 틀을 먼저 나눈 뒤, 그 틀 안에서만 표현을 확장한다.
# 따라서 하나의 원형에서 만든 변형은 한 데이터 분할에만 속한다.
DEFINITIONS = {
    "주문_추가": {
        "subjects": ("아메리카노 한 잔을", "카페라떼 두 잔을", "딸기라떼 한 잔을", "핫초코 세 잔을"),
        "patterns": (
            "{subject} 담아{ending}",
            "{subject} 주문해{ending}",
            "{subject} 장바구니에 넣어{ending}",
            "{subject} 메뉴에 추가해{ending}",
            "{subject} 주문 목록에 넣어{ending}",
            "{subject} 골라{ending}",
            "{subject} 새로 담아{ending}",
            "{subject} 주문에 추가해{ending}",
        ),
    },
    "수량_변경": {
        "subjects": ("아메리카노 수량을 두 잔으로", "카페라떼 수량을 세 잔으로", "딸기라떼 수량을 한 잔으로", "핫초코 수량을 두 잔으로"),
        "patterns": (
            "{subject} 바꿔{ending}",
            "{subject} 수정해{ending}",
            "{subject} 고쳐{ending}",
            "{subject} 변경해{ending}",
            "{subject} 조정해{ending}",
            "{subject} 다시 설정해{ending}",
            "{subject} 정정해{ending}",
            "{subject} 바꾸어{ending}",
        ),
    },
    "주문_삭제": {
        "subjects": ("아메리카노를", "카페라떼를", "딸기라떼를", "핫초코를"),
        "patterns": (
            "주문에서 {subject} 빼{ending}",
            "장바구니에서 {subject} 삭제해{ending}",
            "담아 둔 {subject} 지워{ending}",
            "주문 목록에서 {subject} 제거해{ending}",
            "장바구니에 있는 {subject} 빼{ending}",
            "담았던 {subject} 삭제해{ending}",
            "선택한 {subject} 주문에서 지워{ending}",
            "주문한 {subject} 목록에서 없애{ending}",
        ),
    },
    "메뉴_문의": {
        "subjects": ("아메리카노에 카페인이 있는지", "카페라떼에 우유가 들어가는지", "딸기라떼의 가격이 얼마인지", "핫초코가 어떤 음료인지"),
        "patterns": (
            "{subject} 알려{ending}",
            "{subject} 설명해{ending}",
            "{subject} 말해{ending}",
            "{subject} 확인해{ending}",
            "{subject} 안내해{ending}",
            "{subject} 찾아{ending}",
            "{subject} 살펴봐{ending}",
            "{subject} 확인해서 알려{ending}",
        ),
    },
    "화면_조작": {
        "subjects": ("메뉴 목록을", "화면의 글자를", "메뉴판을", "화면을"),
        "patterns": (
            "{subject} 크게 보여{ending}",
            "{subject} 확대해{ending}",
            "{subject} 더 크게 바꿔{ending}",
            "{subject} 더 잘 보이게 키워{ending}",
            "{subject} 크게 표시해{ending}",
            "{subject} 보기 편하게 확대해{ending}",
            "{subject} 조금 더 크게 해{ending}",
            "{subject} 크게 볼 수 있게 해{ending}",
        ),
    },
    "주문_확인": {
        "subjects": ("주문 내역을", "장바구니를", "내가 고른 메뉴를", "현재 주문 목록을"),
        "patterns": (
            "{subject} 확인해{ending}",
            "{subject} 보여{ending}",
            "{subject} 읽어{ending}",
            "{subject} 알려{ending}",
            "{subject} 다시 보여{ending}",
            "{subject} 한 번 살펴봐{ending}",
            "{subject} 다시 읽어{ending}",
            "{subject} 확인할 수 있게 보여{ending}",
        ),
    },
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser(description="Prepare synthetic CAIFE intent utterances")
    parser.add_argument("--output-dir", type=Path, default=OUT, help="Output directory for CSV, JSONL and manifest")
    OUT = parser.parse_args().output_dir.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    samples = []
    split_groups = {"train": set(), "validation": set(), "test": set()}
    for label, definition in DEFINITIONS.items():
        indices = list(range(len(definition["patterns"])))
        rng.shuffle(indices)
        assignment = {idx: ("train" if pos < 4 else "validation" if pos < 6 else "test")
                      for pos, idx in enumerate(indices)}
        for index, pattern in enumerate(definition["patterns"]):
            group_id = f"{label}_{index + 1:02d}"
            split = assignment[index]
            split_groups[split].add(group_id)
            for subject in definition["subjects"]:
                for ending in ENDINGS:
                    original = pattern.format(subject=subject, ending=ending)
                    normalized = normalize(original)
                    samples.append({
                        "id": hashlib.sha256((group_id + "\0" + original).encode("utf-8")).hexdigest()[:16],
                        "text_raw": original,
                        "text": normalized,
                        "intent": label,
                        "group_id": group_id,
                        "split": split,
                        "source": "직접 작성한 합성 문장",
                    })

    by_text = {}
    duplicates = []
    conflicts = []
    for row in samples:
        key = row["text"]
        previous = by_text.get(key)
        if previous:
            duplicates.append(key)
            if previous["intent"] != row["intent"]:
                conflicts.append(key)
        by_text[key] = row
    overlaps = {
        "train_validation": len(split_groups["train"] & split_groups["validation"]),
        "train_test": len(split_groups["train"] & split_groups["test"]),
        "validation_test": len(split_groups["validation"] & split_groups["test"]),
    }
    cross_split_duplicates = sum(1 for text in set(duplicates)
                                 if len({r["split"] for r in samples if r["text"] == text}) > 1)
    if duplicates or conflicts or any(overlaps.values()) or cross_split_duplicates:
        raise ValueError(f"중복 또는 분할 누수: duplicates={len(duplicates)}, "
                         f"conflicts={len(conflicts)}, overlaps={overlaps}, "
                         f"cross_split_duplicates={cross_split_duplicates}")

    # 실패 시 쓰기 전에 전체 검증한다. 결과 파일은 매번 동일한 순서로 생성된다.
    samples.sort(key=lambda r: (r["split"], r["intent"], r["group_id"], r["text"]))
    fields = ["id", "text_raw", "text", "intent", "group_id", "split", "source"]
    with (OUT / "intents_all.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(samples)
    for split in ("train", "validation", "test"):
        with (OUT / f"{split}.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for row in samples:
                if row["split"] == split:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {
        "dataset": "CAIFE 주문 의도 합성 문장",
        "disclaimer": "직접 작성한 문장 틀을 확장한 합성 텍스트이며 실제 사용자 발화나 음성 인식 데이터가 아님",
        "seed": SEED,
        "group_split_method": "의도별 문장 틀 8개를 seed로 섞어 4/2/2개 분할 후 변형을 생성",
        "total": len(samples),
        "counts_by_intent": dict(sorted(Counter(r["intent"] for r in samples).items())),
        "counts_by_split": dict(sorted(Counter(r["split"] for r in samples).items())),
        "counts_by_split_and_intent": {
            split: dict(sorted(Counter(r["intent"] for r in samples if r["split"] == split).items()))
            for split in ("train", "validation", "test")
        },
        "groups_by_split": {split: len(ids) for split, ids in split_groups.items()},
        "duplicate_normalized_text": len(duplicates),
        "cross_label_conflicts": len(conflicts),
        "cross_split_duplicate_text": cross_split_duplicates,
        "overlapping_groups": overlaps,
        "normalization": "Unicode NFC, 연속 공백 정리, 양 끝 공백 제거. 조사·부정어·수량·온도는 임의로 제거하지 않음",
        "training_status": "주문 의도 분류 모델 학습은 수행하지 않음",
        "limits": [
            "소수의 수작업 템플릿과 고정된 메뉴·수량·존댓말을 조합한 데이터",
            "실제 고객 말투나 STT 오류·소음·다중 의도 및 문맥 의존 발화를 대표하지 않음",
            "원형 그룹을 분리했으나 각 분할의 메뉴명과 문법 패턴이 겹칠 수 있어 실사용 성능을 의미하지 않음",
            "샘플 수가 실제 사용자 발화나 독립적인 문장 원형의 수를 의미하지 않음",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

