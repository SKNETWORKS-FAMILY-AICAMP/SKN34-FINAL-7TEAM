"""API 연결 전 데이터 생성 워크플로 계약. 네트워크 호출이나 주문 실행은 하지 않는다."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Protocol

VERSION = "2"
ROLES = ("question_generator", "action_generator", "supervisor")
ALLOWED_ACTIONS = frozenset({
    "resolve_menu", "ask_clarification", "lookup_menu_attribute",
    "lookup_store_info", "add_to_cart", "change_cart_quantity",
    "remove_cart_item", "show_cart", "guide_customer_to_staff", "change_screen_size",
})
ACTION_CONTRACTS = {
    "add_to_cart": {"menu_id": "자료 ID", "quantity": "1~99의 정수"},
    "lookup_menu_attribute": {"menu_id": "자료 ID"},
    "change_cart_quantity": {"cart_item_id": "주문 항목 자료 ID", "quantity": "1~99의 정수"},
    "remove_cart_item": {"cart_item_id": "주문 항목 자료 ID"},
}
INSTRUCTIONS = {
    "question_generator": (
        "주어진 카페 주문 상황과 제공된 자료를 참고해 고객의 가상 질문을 한 개 작성한다. "
        "제공되지 않은 메뉴나 매장 정보를 사실처럼 만들지 않는다. "
        "실제 고령자의 발언이라고 주장하지 않는다. question 필드에 질문을 반환한다."
    ),
    "action_generator": (
        "질문과 제공된 자료를 바탕으로 필요한 행동과 고객 안내를 제안한다. "
        "정보가 부족하면 재질문하거나 직원 문의를 안내하고 내용을 추측하지 않는다. "
        "actions, customer_reply, source_ids, uncertainties 필드를 반환한다. "
        "구체적 메뉴·장바구니 항목의 ID는 제공된 자료 ID와 일치해야 하며 해당 ID를 source_ids에도 포함한다."
    ),
    "supervisor": (
        "질문, 행동 제안, 제공된 자료를 검토한다. "
        "근거 없는 정보나 누락된 질문 여부를 살펴 verdict(pass 또는 needs_revision), "
        "reason 필드를 반환한다. 최종 승인은 사람이 한다."
    ),
}


class Provider(Protocol):
    """추후 연결할 제공자. 이미 파싱된 JSON 객체만 반환한다."""

    @property
    def model_identifier(self) -> str: ...

    def complete(self, *, role: str, payload: dict[str, Any]) -> Mapping[str, Any]: ...


class WorkflowError(Exception):
    """실패한 단계만 공개하며 API 오류 원문·비밀을 결과에 남기지 않는다."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"{stage}: {message}")


def _text(value: Any, field: str, stage: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise WorkflowError(stage, f"{field}은(는) 비어 있지 않은 {limit}자 이하 문자열이어야 합니다.")
    return value.strip()


def _response(provider: Provider, role: str, payload: dict[str, Any]) -> Mapping[str, Any]:
    try:
        value = provider.complete(role=role, payload=deepcopy(payload))
    except Exception:
        raise WorkflowError(role, "담당자 호출에 실패했습니다.") from None
    if not isinstance(value, Mapping):
        raise WorkflowError(role, "담당자 응답은 JSON 객체여야 합니다.")
    return value


def _facts(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        raise WorkflowError("input", "자료는 목록이어야 합니다.")
    result = []
    used = set()
    for entry in values:
        if not isinstance(entry, Mapping):
            raise WorkflowError("input", "각 자료는 id와 text가 있는 객체여야 합니다.")
        fact_id = _text(entry.get("id"), "자료 ID", "input", 200)
        fact_text = _text(entry.get("text"), "자료 내용", "input", 8000)
        if fact_id in used:
            raise WorkflowError("input", "자료 ID가 중복되었습니다.")
        used.add(fact_id)
        result.append({"id": fact_id, "text": fact_text})
    return result


def _proposal(value: Mapping[str, Any], fact_ids: set[str]) -> dict[str, Any]:
    stage = "action_generator"
    reply = _text(value.get("customer_reply"), "안내 문구", stage)
    actions = value.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > 12:
        raise WorkflowError(stage, "행동은 1~12개의 목록이어야 합니다.")
    ids = value.get("source_ids")
    if not isinstance(ids, list) or any(not isinstance(x, str) or x not in fact_ids for x in ids):
        raise WorkflowError(stage, "출처는 제공된 자료 ID만 사용할 수 있습니다.")
    cited_ids = set(ids)
    clean_actions = []
    for action in actions:
        if not isinstance(action, Mapping):
            raise WorkflowError(stage, "각 행동은 객체여야 합니다.")
        name = _text(action.get("name"), "행동 이름", stage, 100)
        if name not in ALLOWED_ACTIONS:
            raise WorkflowError(stage, "허용되지 않은 행동입니다.")
        arguments = action.get("arguments", {})
        if not isinstance(arguments, Mapping) or any(
            not isinstance(k, str) or not isinstance(v, (str, int, float, bool, type(None)))
            or (isinstance(v, float) and not math.isfinite(v))
            for k, v in arguments.items()
        ):
            raise WorkflowError(stage, "행동 인자는 단순한 JSON 값으로 구성해야 합니다.")
        quantity = arguments.get("quantity")
        if "quantity" in arguments and (type(quantity) is not int or not 1 <= quantity <= 99):
            raise WorkflowError(stage, "수량은 1~99의 정수여야 합니다.")
        if name in ("add_to_cart", "change_cart_quantity") and "quantity" not in arguments:
            raise WorkflowError(stage, "수량이 필요합니다.")
        fact_field = (
            "menu_id" if name in ("add_to_cart", "lookup_menu_attribute")
            else "cart_item_id" if name in ("change_cart_quantity", "remove_cart_item")
            else None
        )
        if fact_field is not None:
            value_id = arguments.get(fact_field)
            if not isinstance(value_id, str) or value_id not in fact_ids or value_id not in cited_ids:
                raise WorkflowError(stage, f"{fact_field}은(는) 제공되고 인용된 자료 ID여야 합니다.")
        clean_actions.append({"name": name, "arguments": dict(arguments)})
    uncertainties = value.get("uncertainties")
    if not isinstance(uncertainties, list) or any(
        not isinstance(x, str) or not x.strip() or len(x) > 1000 for x in uncertainties
    ):
        raise WorkflowError(stage, "미확인 사항은 문자열 목록이어야 합니다.")
    return {"actions": clean_actions, "customer_reply": reply,
            "source_ids": list(dict.fromkeys(ids)), "uncertainties": uncertainties}


def generate_for_human_review(
    provider: Provider, *, scenario: str, source_facts: list[dict[str, str]]
) -> dict[str, Any]:
    """담당자 세 역할을 차례로 실행하고 사람이 검토할 제안만 반환한다.

    반환 데이터는 학습 승인이나 주문 실행이 아니다. 시험용 문장/정답과 개인정보는
    source_facts에 넣지 않고, 학습 데이터 분할은 호출자가 별도로 관리한다.
    """
    scenario = _text(scenario, "상황", "input", 1000)
    facts = _facts(source_facts)
    model = _text(getattr(provider, "model_identifier", None), "모델 식별자", "input", 200)

    question_result = _response(provider, "question_generator", {
        "instruction": INSTRUCTIONS["question_generator"], "scenario": scenario,
        "source_facts": facts,
        "response_format": {"question": "string"},
    })
    question = _text(question_result.get("question"), "질문", "question_generator", 1000)
    proposal_result = _response(provider, "action_generator", {
        "instruction": INSTRUCTIONS["action_generator"], "scenario": scenario,
        "question": question, "source_facts": facts, "allowed_actions": sorted(ALLOWED_ACTIONS),
        "action_contracts": ACTION_CONTRACTS,
        "response_format": {"actions": [{"name": "string", "arguments": {}}],
                            "customer_reply": "string", "source_ids": ["string"],
                            "uncertainties": ["string"]},
    })
    proposal = _proposal(proposal_result, {x["id"] for x in facts})
    review_result = _response(provider, "supervisor", {
        "instruction": INSTRUCTIONS["supervisor"], "scenario": scenario,
        "question": question, "proposal": proposal, "source_facts": facts,
        "response_format": {"verdict": "pass|needs_revision", "reason": "string"},
    })
    verdict = review_result.get("verdict")
    if verdict not in ("pass", "needs_revision"):
        raise WorkflowError("supervisor", "검토 결과는 pass 또는 needs_revision이어야 합니다.")
    reason = _text(review_result.get("reason"), "검토 이유", "supervisor")
    return {
        "schema_version": VERSION,
        "scenario": scenario,
        "question": question,
        "proposal": proposal,
        "ai_review": {"verdict": verdict, "reason": reason},
        "human_review": {"status": "pending"},
        "provenance": {"origin": "synthetic_ai", "model": model,
                       "source_snapshots": [
                           {"id": fact["id"], "text_sha256": hashlib.sha256(
                               fact["text"].encode("utf-8")
                           ).hexdigest()} for fact in facts
                       ],
                       "created_at_utc": datetime.now(timezone.utc).isoformat()},
    }

