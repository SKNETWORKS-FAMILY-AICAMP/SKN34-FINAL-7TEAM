#!/usr/bin/env python3
"""Synthetic contextual/multi-action evaluation; not actual user or STT data."""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

SOURCE = "직접 작성한 합성 텍스트; 실제 고객 음성이나 STT 결과 아님"
# Each group is a wording pattern, retained wholly in one evaluation split.
# Expected actions are specifications, not evidence of implemented features.
# Store policy values and passwords are not included.
GROUPS = [
    ("order_dev", "development", "주문", ["resolve_menu", "validate_required_options", "add_if_complete"], {"menu_ref":"아메리카노", "temperature":"ICE", "quantity":1}, {}, [], ["아이스 아메리카노 한 잔 담아줘", "차가운 아메리카노 하나 주문할게요"]),
    ("order_holdout", "holdout", "주문", ["resolve_menu", "validate_required_options", "add_if_complete"], {"menu_ref":"카페라떼", "temperature":"ICE", "quantity":2}, {}, [], ["차가운 카페라떼 두 잔 부탁해요", "아이스 카페라떼 두 개 주문해 주세요"]),
    ("nutrition_dev", "development", "메뉴정보", ["resolve_context_menu", "lookup_menu_attribute"], {"attribute":"sugar"}, {"selected_menu":"카페라떼"}, [], ["이 음료 당류가 얼마나 돼요?", "지금 고른 거 당은 얼마나 들어가요?"]),
    ("nutrition_holdout", "holdout", "메뉴정보", ["resolve_context_menu", "lookup_menu_attribute"], {"attribute":"caffeine"}, {"selected_menu":"아메리카노"}, [], ["이 커피에 카페인이 들어 있나요?", "지금 선택한 커피 카페인 양이 얼마예요?"]),
    ("allergy_dev", "development", "알레르기", ["resolve_context_menu", "lookup_menu_attribute", "do_not_infer_safety"], {"attribute":"allergen", "ingredient":"우유"}, {"selected_menu":"카페라떼"}, [], ["이거 우유가 들어가나요?", "고른 음료에 우유 알레르기 성분이 있나요?"]),
    ("allergy_holdout", "holdout", "알레르기", ["resolve_context_menu", "lookup_menu_attribute", "do_not_infer_safety"], {"attribute":"allergen", "ingredient":"대두"}, {"selected_menu":"딸기라떼"}, [], ["이 메뉴에 대두가 들어 있어요?", "선택한 음료에 콩 알레르기 성분이 있나요?"]),
    ("volume_dev", "development", "용량", ["resolve_context_menu", "lookup_menu_attribute", "preserve_unit_and_basis"], {"attribute":"serving_size"}, {"selected_menu":"아메리카노"}, [], ["이 음료 용량이 어떻게 되나요?", "고른 음료 한 잔이 얼마나 되나요?"]),
    ("volume_holdout", "holdout", "용량", ["resolve_context_menu", "lookup_menu_attribute", "preserve_unit_and_basis"], {"attribute":"serving_size"}, {"selected_menu":"카페라떼"}, [], ["지금 선택한 음료의 양을 알려주세요", "이 메뉴는 용량이 몇 밀리리터예요?"]),
    ("bathroom_dev", "development", "매장안내", ["lookup_store_info"], {"field":"bathroom_location"}, {}, [], ["화장실 어디에 있어요?", "화장실 위치 좀 알려주세요"]),
    ("bathroom_holdout", "holdout", "매장안내", ["lookup_store_info"], {"field":"bathroom_password"}, {}, [], ["화장실 비밀번호가 뭔가요?", "화장실 이용 비번을 알려주세요"]),
    ("hours_dev", "development", "영업시간", ["lookup_store_info"], {"field":"business_hours"}, {}, [], ["오늘 몇 시까지 영업하나요?", "가게는 언제 문 닫아요?"]),
    ("hours_holdout", "holdout", "영업시간", ["lookup_store_info"], {"field":"business_hours"}, {}, [], ["오전에는 몇 시에 열어요?", "영업 시작 시간 알려주세요"]),
    ("hotwater_dev", "development", "따뜻한물", ["lookup_store_info", "guide_customer_to_staff", "do_not_claim_staff_called"], {"field":"warm_water_policy"}, {}, [], ["따뜻한 물 한 잔 주세요", "미지근한 물 좀 주실 수 있나요?"]),
    ("hotwater_holdout", "holdout", "따뜻한물", ["lookup_store_info", "guide_customer_to_staff", "do_not_claim_staff_called"], {"field":"warm_water_policy"}, {}, [], ["온수 한 컵 부탁드려요", "따뜻한 물을 마시고 싶어요"]),
    ("dialect_dev", "development", "방언표현", ["resolve_menu", "validate_required_options", "add_if_complete"], {"menu_ref":"아메리카노", "temperature":"ICE", "quantity":1}, {}, [], ["아이스 아메리카노 한 잔 주이소", "차가운 아메리카노 하나 주이소"]),
    ("dialect_holdout", "holdout", "방언표현", ["lookup_store_info"], {"field":"bathroom_location"}, {}, [], ["화장실이 어데 있노?", "화장실 어데에 있습니까?"]),
    ("context_dev", "development", "문맥참조", ["resolve_context_menu", "validate_required_options", "add_if_complete"], {"quantity":1}, {"cart":[{"menu_ref":"아메리카노", "temperature":"ICE", "quantity":1}]}, [{"role":"user","text":"아이스 아메리카노 한 잔 담아줘"},{"role":"assistant","text":"아이스 아메리카노 한 잔을 담았어요."}], ["그거 하나 더 담아줘", "방금 고른 음료 한 잔 더 추가해 줘"]),
    ("context_holdout", "holdout", "문맥참조", ["resolve_context_menu", "lookup_menu_attribute"], {"attribute":"calories"}, {"selected_menu":"카페라떼"}, [{"role":"user","text":"카페라떼 보여줘"},{"role":"assistant","text":"카페라떼를 보여드릴게요."}], ["그 음료 칼로리가 얼마예요?", "방금 보여준 것의 열량을 알려줘"]),
    ("multi_dev", "development", "복합요청", ["resolve_menu", "validate_required_options", "add_if_complete", "lookup_store_info"], {"menu_ref":"아메리카노", "temperature":"ICE", "quantity":1, "store_field":"bathroom_location"}, {}, [], ["아이스 아메리카노 하나 담고 화장실 위치도 알려줘", "차가운 아메리카노 한 잔 주문하고 화장실도 알려주세요"]),
    ("multi_holdout", "holdout", "복합요청", ["resolve_context_menu", "lookup_menu_attribute", "lookup_store_info"], {"attribute":"caffeine", "store_field":"business_hours"}, {"selected_menu":"카페라떼"}, [], ["이거 카페인 양과 영업시간을 알려줘", "고른 메뉴 카페인이랑 문 닫는 시간도 알려주세요"]),
    ("ambiguous_dev", "development", "정보누락", ["resolve_menu", "ask_clarification", "do_not_change_cart_before_clarification"], {"menu_ref":"라떼"}, {}, [], ["라떼 한 잔 주세요", "라떼 하나 주문할게요"]),
    ("ambiguous_holdout", "holdout", "정보누락", ["ask_clarification", "do_not_change_cart_before_clarification"], {}, {"cart":[{"menu_ref":"아메리카노", "quantity":1},{"menu_ref":"카페라떼", "quantity":1}]}, [], ["그거 하나 빼줘", "방금 담은 거 하나 삭제해 주세요"]),
    ("unsupported_dev", "development", "미지원", ["check_store_info", "do_not_claim_external_action", "explain_unavailable"], {"request":"주차 정산"}, {}, [], ["주차 요금 정산해 주세요", "차량 주차비 결제해 주세요"]),
    ("unsupported_holdout", "holdout", "미지원", ["check_store_info", "do_not_claim_external_action", "explain_unavailable"], {"request":"택시 호출"}, {}, [], ["택시 좀 불러주세요", "제 대신 택시 호출할 수 있나요?"]),
    ("screen_dev", "development", "화면조작", ["change_screen_size"], {"display":"large"}, {}, [], ["글씨를 더 크게 보여줘요", "화면 확대해서 보여주세요"]),
    ("screen_holdout", "holdout", "화면조작", ["change_screen_size"], {"display":"large"}, {}, [], ["메뉴판 좀 키워 주세요", "글자가 작아서 크게 해 주세요"]),
    ("quantity_dev", "development", "수량변경", ["resolve_context_menu", "change_cart_quantity"], {"quantity":2}, {"cart":[{"menu_ref":"아메리카노","quantity":1}]}, [], ["담은 커피를 두 잔으로 바꿔주세요", "지금 고른 아메리카노를 두 개로 수정해줘"]),
    ("quantity_holdout", "holdout", "수량변경", ["resolve_context_menu", "change_cart_quantity"], {"quantity":3}, {"cart":[{"menu_ref":"카페라떼","quantity":1}]}, [], ["이 라떼 수량을 세 잔으로 해 줘요", "방금 담은 카페라떼를 세 개로 변경해요"]),
    ("delete_dev", "development", "주문삭제", ["resolve_context_menu", "remove_cart_item"], {"menu_ref":"아메리카노"}, {"cart":[{"menu_ref":"아메리카노","quantity":1}]}, [], ["아메리카노를 주문에서 빼 주세요", "담은 아메리카노 항목을 지워 줘요"]),
    ("delete_holdout", "holdout", "주문삭제", ["resolve_context_menu", "remove_cart_item"], {"menu_ref":"카페라떼"}, {"cart":[{"menu_ref":"카페라떼","quantity":1}]}, [], ["카페라떼는 주문 목록에서 없애주세요", "카페라떼 주문 항목을 삭제할게요"]),
    ("cart_dev", "development", "주문확인", ["show_cart"], {}, {"cart":[{"menu_ref":"아메리카노","quantity":1}]}, [], ["담은 음료가 무엇인지 보여줘요", "현재 장바구니 목록을 확인하고 싶어요"]),
    ("cart_holdout", "holdout", "주문확인", ["show_cart"], {}, {"cart":[{"menu_ref":"카페라떼","quantity":1}]}, [], ["내가 주문한 내역을 읽어주세요", "지금까지 고른 메뉴를 확인할게요"]),
]

def normalize(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()

def build_scenarios():
    rows = []
    groups = set()
    texts = set()
    for gid, split, category, actions, slots, state, history, variants in GROUPS:
        if gid in groups or split not in ("development", "holdout") or not actions:
            raise ValueError(f"invalid or duplicate group {gid}")
        groups.add(gid)
        for raw in variants:
            text = normalize(raw)
            if not text or text in texts:
                raise ValueError(f"empty or duplicated text for group {gid}")
            texts.add(text)
            rows.append({
                "scenario_id": hashlib.sha256((gid + "\0" + text).encode("utf-8")).hexdigest()[:16],
                "group_id": gid, "split": split, "category": category,
                "utterance_raw": raw, "utterance": text,
                "conversation_history": history, "current_state": state,
                "expected_actions": actions, "expected_slots": slots,
                "source": SOURCE,
                "note": ("방언풍으로 작성한 텍스트 예시이며 지역 발화를 대표하지 않음"
                         if category == "방언표현" else ""),
            })
    return rows

def validate(rows, baseline_dir=None):
    group_splits, seen = {}, set()
    for row in rows:
        if row["utterance"] in seen:
            raise ValueError("duplicate utterance")
        seen.add(row["utterance"])
        group_splits.setdefault(row["group_id"], set()).add(row["split"])
    if any(len(s) != 1 for s in group_splits.values()):
        raise ValueError("group split overlap")
    matches = 0
    if baseline_dir:
        for split in ("train", "validation", "test"):
            with (baseline_dir / f"{split}.jsonl").open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        matches += normalize(json.loads(line)["text"]) in seen
        if matches:
            raise ValueError(f"baseline exact-text overlap: {matches}")
    return matches

def main():
    parser = argparse.ArgumentParser(description="Prepare contextual multi-action evaluation scenarios")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline-dir", type=Path, help="Existing train/validation/test JSONL for exact-text overlap check")
    args = parser.parse_args()
    rows = build_scenarios()
    matches = validate(rows, args.baseline_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, selected in (("dialogue_evaluation.jsonl", rows),
                           ("dialogue_development.jsonl", [r for r in rows if r["split"] == "development"]),
                           ("dialogue_holdout.jsonl", [r for r in rows if r["split"] == "holdout"])):
        with (args.output_dir / name).open("w", encoding="utf-8", newline="\n") as f:
            for row in selected:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "dataset": "CAIFE 문맥·복합 요청 평가 시나리오", "source": SOURCE,
        "purpose": "개발 및 보류 평가; 기존 6개 단일 분류 학습 데이터를 대체하지 않음",
        "count": len(rows), "group_count": len({r["group_id"] for r in rows}),
        "by_split": dict(Counter(r["split"] for r in rows)),
        "by_category": dict(sorted(Counter(r["category"] for r in rows).items())),
        "group_split_method": "독립 문장 틀 단위로 수작업 분리",
        "cross_split_group_overlap": 0, "duplicate_normalized_text": 0,
        "baseline_exact_overlap": matches if args.baseline_dir else None,
        "limits": [
            "소량의 합성 텍스트이며 실제 고객 발화나 STT 출력이 아님",
            "방언풍 텍스트는 실제 지역 발화나 음성 인식 성능을 대표하지 않음",
            "텍스트 및 그룹 중복 0은 의미상 유사성 또는 학습자료와의 완전 독립을 보장하지 않음",
            "개발과 보류 모두 합성이므로 실사용 평가를 대체하지 못함",
            "정확한 매장·메뉴 답변 값은 등록된 실제 데이터에서 조회하며 이 파일에 만들지 않음",
        ],
    }
    (args.output_dir / "dialogue_scenarios_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()