#!/usr/bin/env python3
"""Preserve raw menu records and build one evidence-backed search document per menu.

Example:
  python scripts/preprocessing/prepare_menus.py --input data/menus/mega/mega_menu.json \
      --output-dir data/menus/mega/processed

The output contains third-party catalog content and must stay subject to the
same handling policy as the input. Never overwrite the original input file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


def clean_text(value):
    """NFC and whitespace normalization; missing values remain None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"문자열이 아닌 값: {type(value).__name__}")
    text = unicodedata.normalize("NFC", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_price(value):
    """Convert only recognizable nonnegative integer won prices; do not guess."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("가격에 불리언 값을 사용할 수 없습니다")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        text = unicodedata.normalize("NFC", value).strip()
        if re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\s*원)?", text):
            return int(re.sub(r"[^\d]", "", text))
    raise ValueError(f"변환할 수 없는 가격: {value!r}")


def has_value(value):
    return value is not None and value != "" and value != []


def normalize_one(raw):
    if not isinstance(raw, dict):
        raise ValueError("메뉴 항목은 객체여야 합니다")
    item_id = clean_text(raw.get("id"))
    name = clean_text(raw.get("name"))
    if not item_id or not name:
        raise ValueError("id와 메뉴명은 필수입니다")
    categories = raw.get("categories")
    if categories is None:
        categories = []
    if not isinstance(categories, list):
        raise ValueError(f"categories가 배열이 아닙니다: {item_id}")
    categories = [text for text in (clean_text(x) for x in categories) if text]
    temp = clean_text(raw.get("temperature"))
    temp = temp.upper() if temp else None
    flags = []
    if temp and temp not in {"HOT", "ICE"}:
        flags.append("unknown_temperature")
    if not has_value(raw.get("caffeine_raw")):
        flags.append("caffeine_missing")
    if not has_value(raw.get("shots")):
        flags.append("shots_structured_missing")
    if not has_value(raw.get("order_options")):
        flags.append("order_options_structured_missing")
    price = parse_price(raw.get("price"))
    if price is None:
        flags.append("price_missing")

    # Text form variants are deterministic. The one colloquial shorthand is a
    # manually curated mapping to the exact iced americano product only.
    aliases = [name]
    compact = name.replace(" ", "")
    if compact != name:
        aliases.append(compact)
    if name == "아메리카노" and temp == "ICE":
        aliases += ["아아", "아이스 아메리카노", "차가운 아메리카노"]
    elif name == "아메리카노" and temp == "HOT":
        aliases += ["핫 아메리카노", "따뜻한 아메리카노"]
    aliases = list(dict.fromkeys(aliases))

    normalized = {
        "id": item_id,
        "name": name,
        "name_en": clean_text(raw.get("name_en")),
        "group": clean_text(raw.get("group")),
        "categories": categories,
        "temperature": temp,
        "price": price,
        "serving_size": clean_text(raw.get("serving_size_raw")),
        "description": clean_text(raw.get("description_raw")),
        "allergen": clean_text(raw.get("allergen_raw")),
        "caffeine": clean_text(raw.get("caffeine_raw")),
        "sugar": clean_text(raw.get("sugar_raw")),
        "aliases": aliases,
        "alias_provenance": "원본 메뉴명·공백 제거; 아메리카노 온도 표현은 수동 사전",
        "source_url": raw.get("source_url"),
        "image_url": raw.get("image_url"),
        "collected_at": raw.get("collected_at"),
        "price_source": raw.get("price_source"),
        "quality_flags": raw.get("quality_flags", []),
        "preprocess_flags": flags,
        # Include every source field unchanged, including unsupported units.
        "raw": raw,
    }
    evidence = []
    for label, value in (
        ("메뉴명", normalized["name"]),
        ("검색 별칭", ", ".join(aliases)),
        ("영문 메뉴명", normalized["name_en"]),
        ("상품 구분", normalized["group"]),
        ("메뉴 분류", ", ".join(categories) or None),
        ("온도", {"ICE": "ICE (차가운 음료)", "HOT": "HOT (따뜻한 음료)"}.get(temp, temp)),
        ("상품 설명", normalized["description"]),
        ("알레르기 원문", normalized["allergen"]),
        ("카페인 원문", normalized["caffeine"]),
        ("당류 원문", normalized["sugar"]),
    ):
        if value:
            evidence.append(f"{label}: {value}")
    search = {
        "menu_id": item_id,
        "name": name,
        "temperature": temp,
        "text": "\n".join(evidence),
        "source_url": raw.get("source_url"),
        "collected_at": raw.get("collected_at"),
        "quality_flags": raw.get("quality_flags", []),
        "preprocess_flags": flags,
    }
    return normalized, search


def process(items):
    if not isinstance(items, list):
        raise ValueError("메뉴 원본은 배열이어야 합니다")
    normalized, documents, seen = [], [], set()
    for raw in items:
        row, doc = normalize_one(raw)
        if row["id"] in seen:
            raise ValueError(f"중복 메뉴 ID: {row['id']}")
        seen.add(row["id"])
        normalized.append(row)
        documents.append(doc)
    if len(normalized) != len(items) or len(documents) != len(items):
        raise AssertionError("원본과 결과의 건수가 일치하지 않습니다")
    return normalized, documents


def alias_index(normalized):
    """Retain every matching menu ID; consumers must disambiguate collisions."""
    candidates = {}
    for row in normalized:
        for alias in row["aliases"]:
            candidates.setdefault(alias, []).append(row["id"])
    return [
        {"alias": alias, "candidate_menu_ids": ids, "candidate_count": len(ids), "ambiguous": len(ids) > 1}
        for alias, ids in sorted(candidates.items())
    ]


def summarize(raw, normalized, docs, aliases, digest):
    missing_keys = ("caffeine_raw", "shots", "order_options", "price", "description_raw", "image_url")
    return {
        "input_sha256": digest,
        "input_records": len(raw),
        "normalized_records": len(normalized),
        "search_documents": len(docs),
        "unique_ids": len({x["id"] for x in normalized}),
        "duplicate_name_temperature_pairs": sum(
            count - 1 for count in Counter((x["name"], x["temperature"]) for x in normalized).values() if count > 1
        ),
        "missing_source_values": {key: sum(not has_value(x.get(key)) for x in raw) for key in missing_keys},
        "raw_description_mentions_shot": sum("샷" in (x.get("description_raw") or "") for x in raw),
        "temperature_counts": dict(Counter(x["temperature"] or "정보 없음" for x in normalized)),
        "input_quality_flag_counts": dict(Counter(flag for row in raw for flag in (row.get("quality_flags") or []))),
        "alias_variants": len(aliases),
        "ambiguous_aliases": sum(item["ambiguous"] for item in aliases),
        "manual_aliases_added": sum(len(x["aliases"]) - len(set([x["name"], x["name"].replace(" ", "")])) for x in normalized),
        "preprocessing": [
            "NFC 및 공백 정규화", "원본 레코드 전체 보존", "ID 유일성 검사", "메뉴별 검색 문서 생성",
            "정보 없음과 원본 품질 표시 보존", "메뉴명 변형 및 검토된 아메리카노 별칭", "충돌 별칭의 모든 후보 보존",
            "근거 없는 가격·영양 정보 생성 안 함"
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="CAIFE 메뉴 정리 및 검색 문서 생성")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raw_bytes = args.input.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8-sig"))
    normalized, docs = process(raw)
    aliases = alias_index(normalized)
    stats = summarize(raw, normalized, docs, aliases, hashlib.sha256(raw_bytes).hexdigest())
    names = {"menus.normalized.json": normalized, "menus.search.json": docs, "menus.aliases.json": aliases, "menus.stats.json": stats}
    source = args.input.resolve()
    for filename in names:
        if (args.output_dir / filename).resolve() == source:
            raise ValueError("출력 경로가 원본과 같습니다")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in names.items():
        (args.output_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
