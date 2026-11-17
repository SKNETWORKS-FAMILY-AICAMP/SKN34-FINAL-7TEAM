#!/usr/bin/env python3
"""Prepare a unified *draft* intent dataset without training a model.

Inputs remain untouched. Existing train/validation/test assignments and human
review identity are preserved; no review approval or missing action is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

SPLITS = ("train", "validation", "test")
ALIASES = {"메뉴_문의": "메뉴_정보"}
ALLOWED = {
    "주문_추가", "수량_변경", "주문_삭제", "메뉴_정보", "화면_조작",
    "주문_확인", "알레르기", "용량", "매장_안내", "서비스_요청", "기타_요청",
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def load_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path.name}:{line_number} JSON 형식 오류") from exc


def convert(raw: dict, dataset: str, file_split: str) -> dict:
    if dataset not in ("single", "multi") or file_split not in SPLITS:
        raise ValueError("지원하지 않는 자료 또는 분할입니다.")
    if raw.get("split") != file_split:
        raise ValueError(f"{dataset}: 파일과 레코드의 분할이 다릅니다.")
    original_id = raw.get("id") if dataset == "single" else raw.get("scenario_id")
    group_id = raw.get("group_id")
    original_text = raw.get("text_raw") if dataset == "single" else raw.get("utterance_raw")
    text = raw.get("text") or raw.get("utterance")
    labels = [raw.get("intent")] if dataset == "single" else raw.get("intents")
    if not all(isinstance(v, str) and v.strip() for v in (original_id, group_id, original_text, text)):
        raise ValueError("ID, 그룹, 원문 및 문장이 필요합니다.")
    if not isinstance(labels, list) or not labels or not all(isinstance(x, str) for x in labels):
        raise ValueError("의도 라벨이 없습니다.")
    canonical = [ALIASES.get(label, label) for label in labels]
    if len(set(canonical)) != len(canonical) or not set(canonical).issubset(ALLOWED):
        raise ValueError("알 수 없거나 중복된 의도 라벨입니다.")
    if dataset == "single":
        review_source = "단일 의도"
    else:
        # The review app loads the development/holdout original view for these IDs.
        review_source = "다중 의도 학습" if file_split == "train" else "문맥 시나리오"
    return {
        "id": f"{dataset}:{original_id}",
        "original_id": original_id,
        "review_key": f"{review_source}:{original_id}",
        "dataset": dataset,
        "split": file_split,
        "group_id": group_id,
        "text_raw": original_text,
        "text": normalize(text),
        "intents": canonical,
        "original_intents": labels,
        "annotation_scope": "single_intent_only" if dataset == "single" else "multi_intent_draft",
        "annotation_complete": False if dataset == "single" else None,
        "expected_actions": raw.get("expected_actions", []),
        "expected_slots": raw.get("expected_slots", {}),
        "conversation_history": raw.get("conversation_history", []),
        "current_state": raw.get("current_state", {}),
        "category": raw.get("category"),
        "source": raw.get("source"),
        "note": raw.get("note"),
    }


def validate(rows):
    ids = set()
    groups = defaultdict(set)
    texts = defaultdict(set)
    for row in rows:
        if row["id"] in ids:
            raise ValueError("중복된 데이터 ID가 있습니다.")
        ids.add(row["id"])
        # Group IDs from different datasets are not necessarily the same template.
        groups[(row["dataset"], row["group_id"])].add(row["split"])
        texts[row["text"]].add(row["split"])
    split_groups = sum(len(splits) > 1 for splits in groups.values())
    split_texts = sum(len(splits) > 1 for splits in texts.values())
    if split_groups or split_texts:
        raise ValueError(f"분할 간 누수: 그룹 {split_groups}건, 동일 문장 {split_texts}건")
    return {"cross_split_groups": split_groups, "cross_split_exact_texts": split_texts}


def prepare(root: Path):
    data = root / "data"
    files = [
        *((data / "intents" / "processed" / f"{s}.jsonl", "single", s) for s in SPLITS),
        *((data / "dialogue" / "processed" / f"dialogue_multilabel_{s}.jsonl", "multi", s) for s in SPLITS),
    ]
    rows, hashes = [], {}
    for path, dataset, split in files:
        if not path.is_file():
            raise FileNotFoundError(f"입력 파일이 없습니다: {path}")
        hashes[str(path.relative_to(root)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.extend(convert(raw, dataset, split) for raw in load_jsonl(path))
    checks = validate(rows)
    rows.sort(key=lambda r: (SPLITS.index(r["split"]), r["dataset"], r["id"]))
    by_split = Counter(row["split"] for row in rows)
    by_dataset = Counter(row["dataset"] for row in rows)
    label_counts = Counter(label for row in rows for label in row["intents"])
    manifest = {
        "purpose": "사람이 아직 최종 승인하지 않은 기존 합성 문장의 형식 정리",
        "total": len(rows),
        "by_split": dict(sorted(by_split.items())),
        "by_dataset": dict(sorted(by_dataset.items())),
        "intent_counts": dict(sorted(label_counts.items())),
        "label_mapping": ALIASES,
        "validation": checks,
        "input_sha256": hashes,
        "limits": [
            "기존 합성 텍스트이며 실제 음성이나 고객 발화가 아닙니다.",
            "기존 문장의 사람 검토 상태는 이 파일에 반영하지 않았습니다.",
            "단일 의도 자료에는 세부 복합 라벨이 없으므로 누락된 라벨을 부정 사례로 취급하지 않습니다.",
            "행동·주문 정보가 없는 경우 만들어내지 않고 빈 상태를 유지했습니다.",
            "정확한 동일 문장과 그룹만 검사했으며 의미적으로 비슷한 문장은 중복될 수 있습니다.",
            "훈련·검증·시험 분할은 원본을 유지합니다. 모델 학습은 수행하지 않았습니다.",
        ],
    }
    return rows, manifest


def write_new_output(output: Path, rows: list, manifest: dict):
    # Prevent accidentally overwriting previous data or any input directory.
    output.mkdir(parents=True, exist_ok=False)
    for split in SPLITS:
        with (output / f"{split}.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                if row["split"] == split:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description="기존 합성 질문의 의도 라벨과 데이터 형식 통일")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="아직 존재하지 않는 결과 폴더")
    args = parser.parse_args()
    root, output = args.project_root.resolve(), args.output_dir.resolve()
    rows, manifest = prepare(root)
    write_new_output(output, rows, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

