#!/usr/bin/env python3
"""Validate a local demonstration store profile and prepare FAQ records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def require_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"필수 항목이 없거나 문자열이 아닙니다: {key}")
    return " ".join(value.split())


def build_facts(store):
    if not isinstance(store, dict):
        raise ValueError("매장 원본은 JSON 객체여야 합니다")
    restroom = require_text(store, "restroom_location")
    passcode = require_text(store, "restroom_passcode")
    water = require_text(store, "warm_water_guidance")
    opens = require_text(store, "opens_at")
    closes = require_text(store, "closes_at")
    for value in (opens, closes):
        try:
            hour, minute = value.split(":")
            if len(hour) != 2 or len(minute) != 2 or not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("시간은 00:00부터 23:59까지 HH:MM 형식이어야 합니다") from None
    facts = [
        {"id": "restroom.location", "topic": "화장실 위치", "value": restroom,
         "applies_to": ["남성", "여성"], "source": "사용자가 제공한 가상 매장 설정"},
        {"id": "restroom.passcode", "topic": "화장실 비밀번호", "value": passcode,
         "applies_to": ["남성", "여성"], "customer_visible": True,
         "source": "사용자가 제공한 가상 매장 설정"},
        {"id": "service.warm_water", "topic": "따뜻한 물", "value": water,
         "fulfillment": "직원에게 직접 문의", "source": "사용자가 제공한 가상 매장 설정"},
        {"id": "hours.open", "topic": "영업 시작 시간", "value": opens,
         "days": None, "source": "사용자가 제공한 가상 매장 설정"},
        {"id": "hours.close", "topic": "영업 종료 시간", "value": closes,
         "days": None, "source": "사용자가 제공한 가상 매장 설정"},
    ]
    return {"store_id": require_text(store, "store_id"), "demo": True, "facts": facts,
            "unknown": ["영업 요일", "휴무일", "공휴일 영업시간", "엘리베이터 여부"]}


def main():
    parser = argparse.ArgumentParser(description="가상 매장 정보 검증 및 조회 자료 생성")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError("원본과 결과 경로는 달라야 합니다")
    data = json.loads(args.input.read_text(encoding="utf-8-sig"))
    result = build_facts(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"가상 매장 안내 {len(result['facts'])}항목 생성")


if __name__ == "__main__":
    main()
