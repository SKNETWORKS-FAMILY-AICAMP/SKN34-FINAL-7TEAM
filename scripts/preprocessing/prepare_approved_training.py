#!/usr/bin/env python3
"""사람이 승인한 검토 결과만 통일된 학습 초안에 결합한다.

입력 파일과 기존 출력을 바꾸지 않는다. 수정된 문장은 의도 라벨을 다시
확인할 때까지 별도로 보관한다. LLM 호출이나 모델 학습은 수행하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open(encoding="utf-8-sig") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path.name}:{line_number} JSON 형식 오류") from e
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number} 객체가 아닙니다.")
            out.append(row)
    return out


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}이(가) 없거나 올바르지 않습니다.")
    return value.strip()


def build(sets: dict[str, list[dict]], reviews: list[dict]) -> tuple[list[dict], dict]:
    indexed = {}
    eval_texts = set()
    for split in ("train", "validation", "test"):
        if split not in sets:
            raise ValueError("학습·검증·시험 초안이 모두 필요합니다.")
        for row in sets[split]:
            key = nonempty(row.get("review_key"), "초안 질문 ID")
            if row.get("split") != split:
                raise ValueError("초안의 분할이 파일과 일치하지 않습니다.")
            if key in indexed:
                raise ValueError("초안 질문 ID가 중복되었습니다.")
            nonempty(row.get("text"), "초안 질문")
            labels = row.get("intents")
            if not isinstance(labels, list) or not labels or any(not isinstance(v, str) or not v.strip() for v in labels):
                raise ValueError("초안 의도 라벨이 올바르지 않습니다.")
            indexed[key] = row
            if split != "train":
                eval_texts.add(normalized(row["text"]))

    if not reviews:
        raise ValueError("승인된 학습용 질문이 없습니다.")
    seen = set()
    seen_questions = set()
    records = []
    for review in reviews:
        key = nonempty(review.get("question_id"), "검토 질문 ID")
        if key in seen:
            raise ValueError("승인 파일에 중복된 질문 ID가 있습니다.")
        seen.add(key)
        if review.get("review_status") != "승인":
            raise ValueError("승인 상태가 아닌 질문이 있거나 승인 상태가 없습니다. 최신 화면에서 다시 내려받아 주세요.")
        if review.get("original_split") != "train":
            raise ValueError("학습용이 아닌 검토 결과가 포함되어 있습니다.")
        draft = indexed.get(key)
        if draft is None:
            raise ValueError("검토 질문에 해당하는 초안을 찾지 못했습니다.")
        if draft["split"] != "train":
            raise ValueError("검증·시험용 질문은 학습 데이터로 결합할 수 없습니다.")
        if review.get("group_id") != draft.get("group_id"):
            raise ValueError("검토 문장의 원본 그룹이 일치하지 않습니다.")
        source_question = nonempty(review.get("question_original"), "원본 질문")
        if normalized(source_question) != normalized(draft["text"]):
            raise ValueError("검토 질문의 원문과 초안이 일치하지 않습니다.")
        question = nonempty(review.get("question_approved"), "승인 질문")
        action = nonempty(review.get("expected_action"), "승인된 처리 방법")
        reviewed_at = nonempty(review.get("reviewed_at_utc"), "평가 일시")
        answer = review.get("expected_answer", "")
        comment = review.get("review_comment", "")
        if not isinstance(answer, str) or not isinstance(comment, str):
            raise ValueError("안내 문구와 의견은 문자열이어야 합니다.")
        if normalized(question) in eval_texts:
            raise ValueError("승인 질문이 검증·시험 문장과 정확히 일치합니다.")
        if normalized(question) in seen_questions:
            raise ValueError("승인된 질문 문장이 중복되었습니다.")
        seen_questions.add(normalized(question))
        changed = question != source_question
        records.append({
            **draft,
            "review_status": "승인",
            "question_approved": question,
            "expected_action_approved": action,
            "expected_answer_approved": answer,
            "review_comment": comment,
            "reviewed_at_utc": reviewed_at,
            "label_review_required": changed,
        })
    return records, {
        "approved_count": len(records),
        "ready_count": sum(not row["label_review_required"] for row in records),
        "label_review_required_count": sum(row["label_review_required"] for row in records),
        "limitations": [
            "검토 JSONL은 신뢰할 수 있는 CAIFE 검토 화면에서 내려받은 파일이어야 합니다.",
            "문장이 바뀐 경우 기존 의도 라벨이 맞는지 사람이 확인하기 전까지 학습용에서 제외합니다.",
            "검증·시험 문장과 정확히 일치하는 경우는 거부하며 의미상 유사성은 별도로 검토해야 합니다.",
            "실제 고객 발화가 아닌 합성 문장입니다. 모델 학습은 수행하지 않았습니다.",
        ],
    }


def write_new_output(path: Path, records: list[dict], manifest: dict):
    path.mkdir(parents=True, exist_ok=False)
    for name, rows in (
        ("approved_all.jsonl", records),
        ("training_ready.jsonl", [r for r in records if not r["label_review_required"]]),
        ("needs_label_review.jsonl", [r for r in records if r["label_review_required"]]),
    ):
        with (path / name).open("x", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="승인된 학습용 질문을 전처리 초안과 결합")
    parser.add_argument("--unified-dir", type=Path, required=True, help="train/validation/test.jsonl이 있는 초안 폴더")
    parser.add_argument("--approved-file", type=Path, required=True, help="CAIFE 검토 화면에서 내려받은 승인 JSONL")
    parser.add_argument("--output-dir", type=Path, required=True, help="아직 존재하지 않는 결과 폴더")
    args = parser.parse_args()
    inputs = {split: args.unified_dir / f"{split}.jsonl" for split in ("train", "validation", "test")}
    sets = {split: read_jsonl(path) for split, path in inputs.items()}
    reviews = read_jsonl(args.approved_file)
    records, manifest = build(sets, reviews)
    manifest["input_sha256"] = {
        **{split: hashlib.sha256(path.read_bytes()).hexdigest() for split, path in inputs.items()},
        "approved_file": hashlib.sha256(args.approved_file.read_bytes()).hexdigest(),
    }
    write_new_output(args.output_dir, records, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

