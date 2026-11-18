import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MENU_TOPICS = {
    "serving_size": r"용량|사이즈|크기|몇미리|몇밀리|몇ml|몇온스",
    "calories": r"칼로리|열량|kcal",
    "sugar": r"당류|당도|설탕|(?:덜|안)달|단맛",
    "caffeine": r"카페인",
    "sodium": r"나트륨",
    "protein": r"단백질",
    "saturated_fat": r"포화지방",
    "allergens": r"알레르기|알러지|알레르겐|우유|유당|견과|땅콩|달걀|계란|대두|밀가루",
}
DIRECT_INFO = re.compile(r"얼마|몇|알려|어디|있[어냐나습]|들어가|들어갔|들었|포함|어때|뭐야|뭐예|궁금|추천|(?:용량|카페인|알레르기|영양정보|칼로리|당류)$")
ORDER_REQUEST = re.compile(r"(?:[0-9]+|한|두|세|네|다섯)(?:잔|개)(?:주|담|주문|하고|이?랑|도)|(?:담아|추가해|결제해|주문할|주문해|빼줘|바꿔줘)")


def compact(value):
    return re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFKC", value).lower())


def read_json(path, expected):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return expected()
    return value if isinstance(value, expected) else expected()


def menu_topics(message):
    topics = [name for name, pattern in MENU_TOPICS.items() if re.search(pattern, message)]
    if re.search(r"영양(?:정보|성분)|영양표", message):
        topics.extend(topic for topic in ("calories", "sugar", "caffeine") if topic not in topics)
    return topics


class OrderEvidence:
    def __init__(self, menus, aliases, store):
        self.menus = {item["id"]: item for item in menus if isinstance(item, dict)
                      and isinstance(item.get("id"), str) and isinstance(item.get("name"), str)}
        self.aliases = {}
        for row in aliases:
            if not isinstance(row, dict) or not isinstance(row.get("alias"), str):
                continue
            name = compact(row["alias"])
            if len(name) >= 2:
                self.aliases.setdefault(name, set()).update(
                    menu_id for menu_id in row.get("candidate_menu_ids", []) if menu_id in self.menus
                )
        americano = [key for key, item in self.menus.items() if item.get("name") == "아메리카노" and item.get("temperature") == "ICE"]
        for name in ("아아", "아아메"):
            self.aliases.setdefault(name, set()).update(americano)
        for key, item in self.menus.items():
            self.aliases.setdefault(compact(item["name"]), set()).add(key)
        self.store = {
            fact["id"]: fact for fact in store.get("facts", [])
            if isinstance(fact, dict) and fact.get("id") and fact.get("value")
            and fact.get("customer_visible") is not False
            and (fact["id"] != "restroom.passcode" or fact.get("customer_visible") is True)
        } if store.get("demo") is True else {}

    @classmethod
    def from_storage(cls):
        menu_file = Path(os.environ.get("CAIFE_MENU_DATA_FILE", ROOT / "data/menus/mega/mega_menu.json"))
        folder = Path(os.environ.get("CAIFE_MENU_FACTS_DIR", menu_file.parent / "processed_v2"))
        store_file = Path(os.environ.get("CAIFE_STORE_FACTS_FILE", ROOT / "data/store/store.facts.json"))
        return cls(read_json(folder / "menus.normalized.json", list),
                   read_json(folder / "menus.aliases.json", list), read_json(store_file, dict))

    def menu_ids(self, message):
        ids = set()
        spans = []
        for alias in sorted(self.aliases, key=len, reverse=True):
            if not alias:
                continue
            for match in re.finditer(re.escape(alias), message):
                start, end = match.span()
                if any(start < right and end > left for left, right in spans):
                    continue
                spans.append((start, end))
                ids.update(self.aliases[alias])
        hot = bool(re.search(r"따뜻|뜨거|뜨겁|핫", message))
        ice = bool(re.search(r"아이스|차갑|차가|시원", message))
        if spans and len(spans) == 1 and hot != ice:
            filtered = {menu_id for menu_id in ids if self.menus[menu_id].get("temperature") == ("HOT" if hot else "ICE")}
            return filtered
        return ids

    def select(self, transcript, history, state):
        message = compact(transcript)
        topics = menu_topics(message)
        ids = self.menu_ids(message)
        pending = state.get("pending") or {}
        drafts = pending.get("items")
        pending_ids = {key for entry in drafts if isinstance(entry, dict) and isinstance(entry.get("menu_ids"), list)
                       for key in entry["menu_ids"] if isinstance(key, str)} if pending.get("purpose") == "info" and isinstance(drafts, list) else set()
        info_followup = False
        if not topics and ids.intersection(pending_ids) and not ORDER_REQUEST.search(message):
            for entry in reversed(history):
                if entry["role"] == "customer":
                    topics = menu_topics(compact(entry["text"]))
                    if topics:
                        info_followup = True
                        break
        if topics and not ids and re.search(r"이거|그거|아까|이메뉴|그메뉴|방금|이음료|그음료|이건|그건", message):
            option = state.get("options") or {}
            if isinstance(option.get("menu_id"), str) and option["menu_id"] in self.menus:
                ids = {option["menu_id"]}
            else:
                ids = {line["menu_id"] for line in state.get("cart", []) if isinstance(line.get("menu_id"), str) and line["menu_id"] in self.menus}
                if not ids:
                    for entry in reversed(history):
                        if entry["role"] == "customer":
                            ids = self.menu_ids(compact(entry["text"]))
                            if ids:
                                break
        keys = []
        if re.search(r"화장실|변소", message):
            if re.search(r"비번|비밀번호|암호", message):
                keys.append("restroom.passcode")
            if not keys or re.search(r"어디|위치", message):
                keys.append("restroom.location")
        if re.search(r"(?:뜨거운|따뜻한|온)물", message):
            keys.append("service.warm_water")
        hours = re.search(r"영업시간|문(?:여|열|닫)|오픈|마감|몇시(?:까지|부터|에)|오늘쉬|휴무|공휴일", message)
        if hours:
            keys.extend(("hours.open", "hours.close"))
        unknown_store = bool(re.search(r"와이파이|wifi|주차|엘리베이터|라스트오더|공휴일|휴무|(?:오늘|내일|토요일|일요일|주말|평일).*(?:영업|여나요|열어요|하나요|쉬나요)", message))
        decaf = bool(re.search(r"디카페인|카페인(?:이)?(?:적|없는|낮|없이|빼)", message))
        return {
            "menu_topics": topics, "menu_status": "ambiguous" if len(ids) > 1 else "available" if ids
            else ("need_menu" if self.menus else "unavailable") if topics else "none",
            "match_count": len(ids), "decaf_requested": decaf,
            "info_followup": info_followup,
            "menus": [
                {"menu_id": key, "name": item["name"], "temperature": item.get("temperature"),
                 "description": item.get("description"), "facts": item.get("menu_facts", {})}
                for key, item in self.menus.items() if key in ids
            ][:12],
            "store_topics": keys, "store_facts": [self.store[key] for key in keys if key in self.store],
            "unknown_store_facts": unknown_store,
        }


def local_information_action(transcript, evidence, categories, state):
    message = compact(transcript)
    topics = evidence["menu_topics"]
    matches = evidence["menus"]
    if ORDER_REQUEST.search(message):
        return None
    if evidence["unknown_store_facts"] and not evidence["store_facts"]:
        return {"type": "inform", "text": "그 매장 정보는 등록되어 있지 않아요. 직원에게 문의해 주세요."}
    if evidence["store_topics"] and not topics:
        facts = {row["id"]: row["value"] for row in evidence["store_facts"]}
        if not facts:
            return {"type": "inform", "text": "등록된 매장 안내가 없어요. 직원에게 문의해 주세요."}
        replies = [str(facts[key]) for key in ("restroom.location", "service.warm_water") if key in facts]
        if "restroom.passcode" in facts:
            replies.append("화장실 비밀번호는 " + str(facts["restroom.passcode"]) + "예요.")
        if "hours.open" in facts and "hours.close" in facts:
            replies.append(f"등록된 영업시간은 {facts['hours.open']}부터 {facts['hours.close']}까지예요.")
        if evidence["unknown_store_facts"]:
            replies.append("요일이나 추가 매장 정보는 직원에게 문의해 주세요.")
        return {"type": "inform", "text": " ".join(replies) or "직원에게 문의해 주세요."}
    if evidence["decaf_requested"] and not matches and set(topics) <= {"caffeine"} and "디카페인" in categories:
        return {"type": "show_category", "category": "디카페인"}
    if not topics or (not DIRECT_INFO.search(message) and not evidence["info_followup"]):
        return None
    if evidence["menu_status"] == "unavailable":
        return {"type": "inform", "text": "메뉴 정보를 불러오지 못했어요. 직원에게 문의해 주세요."}
    if not matches:
        return {"type": "inform", "text": "정보가 궁금한 메뉴 이름을 말씀해 주세요."}
    if evidence["match_count"] > 1:
        if state.get("rule_draft") or (state.get("pending") and state["pending"].get("purpose") != "info"):
            return {"type": "inform", "text": "정보가 궁금한 메뉴의 이름과 온도를 함께 말씀해 주세요."}
        labels = [{"ICE": "아이스 ", "HOT": "핫 "}.get(item["temperature"], "") + item["name"] for item in matches]
        return {"type": "ask", "field": "menu", "purpose": "info", "text": "어떤 메뉴의 정보를 알려드릴까요?",
                "items": [{"menu_ids": [item["menu_id"]]} for item in matches[:8]], "choices": list(dict.fromkeys(labels))[:4]}
    facts = matches[0]["facts"]
    replies = []
    for topic in topics:
        if topic == "allergens":
            allergens = facts.get("allergens") or {}
            ingredients = allergens.get("items") or []
            if allergens.get("status") == "available" and ingredients:
                replies.append("표시된 알레르기 성분은 " + ", ".join(ingredients) + "예요. 교차 접촉 여부는 직원에게 문의해 주세요.")
            else:
                replies.append("알레르기 정보를 확실히 확인하기 어려워요. 직원에게 문의해 주세요.")
            continue
        fact = facts.get(topic) if topic == "serving_size" else (facts.get("nutrition") or {}).get(topic)
        if fact and fact.get("status") == "available" and fact.get("raw"):
            label = "컵 용량 기준 " if topic == "serving_size" and fact.get("kind") == "cup_capacity" else ""
            replies.append(label + str(fact["raw"]) + ".")
        else:
            replies.append("해당 값은 등록된 자료에서 확인하기 어려워요.")
    return {"type": "inform", "text": (" ".join(replies))[:280], "clear_info": True}
