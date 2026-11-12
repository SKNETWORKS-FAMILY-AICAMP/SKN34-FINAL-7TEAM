#!/usr/bin/env python3
"""Create synthetic multi-label training data and independent scenario evaluation splits.

Small demonstration set: not representative of real speech or real customers.
Never place actual store passwords, nutrition values, or private information here.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import prepare_dialogue_scenarios as scenarios

# 16 training wording groups, distinct from all scenario development/test groups.
# Intents describe customer requests, not tool outcomes. Multi-intent remains an array.
# Each pair is manually written: number of rows is not number of real speakers.
TRAIN = [
  ("train_order","주문",["주문_추가"],["아이스 아메리카노를 한 잔 주세요","차가운 아메리카노를 하나 담아 주세요"],{},[]),
  ("train_nutrition","메뉴정보",["메뉴_정보"],["선택한 음료는 당이 얼마나 되나요","고른 음료에 들어간 당류를 알고 싶어요"],{"selected_menu":"카페라떼"},[]),
  ("train_allergy","알레르기",["메뉴_정보","알레르기"],["이 음료에 우유 성분이 포함되어 있습니까","고른 메뉴 우유 알레르기 정보를 보여줘요"],{"selected_menu":"카페라떼"},[]),
  ("train_volume","용량",["메뉴_정보","용량"],["한 잔에 몇 밀리리터가 들어가죠","이 음료 크기가 얼마인지 알려줘요"],{"selected_menu":"아메리카노"},[]),
  ("train_bathroom","매장안내",["매장_안내"],["이 매장 화장실은 어디로 가면 돼요","손 씻으려면 어디로 가나요"],{},[]),
  ("train_hours","영업시간",["매장_안내"],["매장은 언제까지 열려 있어요","가게 문을 몇 시에 여나요"],{},[]),
  ("train_water","따뜻한물",["서비스_요청"],["따뜻하게 마실 물을 받을 수 있나요","데운 물 한 컵을 주실래요"],{},[]),
  ("train_dialect","방언표현",["매장_안내"],["화장실이 어디 있습니꺼","화장실 어딘지 좀 갈쳐주이소"],{},[]),
  ("train_context","문맥참조",["주문_추가"],["방금 주문한 것을 한 잔 더 주세요","방금 담은 음료를 하나 추가해주세요"],{"cart":[{"menu_ref":"아메리카노","temperature":"ICE","quantity":1}]},[{"role":"user","text":"아이스 아메리카노 한 잔 담아줘"},{"role":"assistant","text":"아이스 아메리카노 한 잔을 담았어요."}]),
  ("train_multi","복합요청",["메뉴_정보","매장_안내"],["고른 음료 열량이랑 화장실 위치를 알려줘요","이 메뉴 칼로리하고 화장실 어디인지 같이 알려주세요"],{"selected_menu":"카페라떼"},[]),
  ("train_ambiguous","정보누락",["주문_추가"],["라떼를 하나 마시고 싶어요","라떼 한 잔 부탁합니다"],{},[]),
  ("train_unsupported","미지원",["기타_요청"],["주차권을 등록해 줄 수 있나요","자동차 주차권을 처리해 주세요"],{},[]),
  ("train_screen","화면조작",["화면_조작"],["글자가 잘 안 보여서 키워 주세요","화면이 작으니 크게 표시해 주세요"],{},[]),
  ("train_quantity","수량변경",["수량_변경"],["담은 아메리카노의 개수를 두 잔으로 고쳐줘요","아메리카노 주문량을 두 개로 조절해 주세요"],{"cart":[{"menu_ref":"아메리카노","quantity":1}]},[]),
  ("train_delete","주문삭제",["주문_삭제"],["아메리카노는 주문에서 제거할게요","담아둔 아메리카노를 없애주세요"],{"cart":[{"menu_ref":"아메리카노","quantity":1}]},[]),
  ("train_cart","주문확인",["주문_확인"],["내 장바구니 내용을 알려줘요","주문 목록에 뭐가 있는지 볼게요"],{"cart":[{"menu_ref":"아메리카노","quantity":1}]},[]),
]

# Categories require customer-intent labels, not the programmer's tool names.
# No single-label coercion: distinct requests remain separate values.
LABELS = {
  "주문":["주문_추가"], "메뉴정보":["메뉴_정보"], "알레르기":["메뉴_정보","알레르기"],
  "용량":["메뉴_정보","용량"], "매장안내":["매장_안내"], "영업시간":["매장_안내"],
  "따뜻한물":["서비스_요청"], "미지원":["기타_요청"], "화면조작":["화면_조작"],
  "수량변경":["수량_변경"], "주문삭제":["주문_삭제"], "주문확인":["주문_확인"],
}

def eval_labels(row):
    cat = row["category"]
    actions = row["expected_actions"]
    if cat == "방언표현":
        return ["매장_안내"] if "lookup_store_info" in actions else ["주문_추가"]
    if cat == "문맥참조":
        return ["메뉴_정보"] if "lookup_menu_attribute" in actions else ["주문_추가"]
    if cat == "복합요청":
        return (["메뉴_정보","매장_안내"] if "lookup_menu_attribute" in actions
                else ["주문_추가","매장_안내"])
    if cat == "정보누락":
        return ["주문_삭제"] if row["group_id"] == "ambiguous_holdout" else ["주문_추가"]
    return LABELS[cat]

def build():
    train = []
    for group, category, labels, variants, state, history in TRAIN:
        for raw in variants:
            text = scenarios.normalize(raw)
            train.append({
                "scenario_id": hashlib.sha256((group+"\0"+text).encode("utf-8")).hexdigest()[:16],
                "group_id":group, "split":"train", "category":category,
                "utterance_raw":raw, "utterance":text, "intents":labels,
                "conversation_history":history, "current_state":state,
                "expected_actions":[], "expected_slots":{}, "source":scenarios.SOURCE,
            })
    evaluation = scenarios.build_scenarios()
    for row in evaluation:
        row["intents"] = eval_labels(row)
        row["split"] = {"development":"validation","holdout":"test"}[row["split"]]
    rows = train + evaluation
    # A standard text key makes downstream training independent of the evaluation format.
    for row in rows:
        row["text"] = row["utterance"]
    seen = set()
    group_splits = {}
    ids = set()
    for row in rows:
        if row["utterance"] in seen:
            raise ValueError("duplicate utterance: "+row["utterance"])
        seen.add(row["utterance"])
        if row["scenario_id"] in ids:
            raise ValueError("duplicate ID")
        ids.add(row["scenario_id"])
        group_splits.setdefault(row["group_id"],set()).add(row["split"])
        if not row["intents"] or len(row["intents"]) != len(set(row["intents"])):
            raise ValueError("invalid intents")
    if any(len(splits) != 1 for splits in group_splits.values()):
        raise ValueError("group leakage across splits")
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir",required=True,type=Path)
    ap.add_argument("--baseline-dir",type=Path)
    args=ap.parse_args()
    rows=build()
    exact_overlap=0
    if args.baseline_dir:
        texts={r["utterance"] for r in rows}
        for split in ("train","validation","test"):
            with (args.baseline_dir/f"{split}.jsonl").open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        exact_overlap += scenarios.normalize(json.loads(line)["text"]) in texts
        if exact_overlap:
            raise ValueError(f"baseline exact utterance overlap: {exact_overlap}")
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for split in ("train","validation","test"):
        with (args.output_dir/f"dialogue_multilabel_{split}.jsonl").open("w",encoding="utf-8",newline="\n") as f:
            for row in rows:
                if row["split"] == split:
                    f.write(json.dumps(row,ensure_ascii=False)+"\n")
    manifest={
        "dataset":"CAIFE 문맥·다중 의도 합성 문장", "source":scenarios.SOURCE,
        "purpose":"다중 의도 분류기 학습 및 별도 평가 준비; 실제 모델 학습은 수행하지 않음",
        "total":len(rows), "counts_by_split":dict(Counter(r["split"] for r in rows)),
        "groups_by_split":{s:len({r["group_id"] for r in rows if r["split"]==s}) for s in ("train","validation","test")},
        "counts_by_label":dict(sorted(Counter(label for row in rows for label in row["intents"]).items())),
        "split_method":"수작업으로 독립 문장 틀을 지정해 분할한 후 틀별 문장 변형을 생성",
        "exact_duplicate_utterances":0, "group_leakage_across_splits":0,
        "baseline_exact_overlap":exact_overlap if args.baseline_dir else None,
        "limits":[
          "직접 작성한 소량의 합성 텍스트로 실제 고객 발화·음성·STT 출력이 아님",
          "구어체 및 사투리풍 문장은 실제 지역 화자와 발음 특성을 대표하지 않음",
          "그룹 및 정확 중복 제거가 의미 유사성 또는 완전한 통계적 독립을 보장하지 않음",
          "작은 학습 데이터는 모델 성능·실사용 적합성을 평가하기에 부족하며 별도의 실측 평가가 필요함",
          "매장 비밀번호 및 실제 메뉴 영양값은 포함하지 않고 결과 확인 시 데이터 저장소에서 조회함",
          "다중 의도 라벨은 수동 설계한 초안으로 일관성과 품질을 보완해야 함",
        ],
    }
    (args.output_dir/"dialogue_multilabel_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()