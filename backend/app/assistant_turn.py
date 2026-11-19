import os
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .assistant_evidence import OrderEvidence, local_information_action
from .openai_order import OrderProviderError, decide_order

router = APIRouter(prefix="/api/assistant")

TurnText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class HistoryEntry(BaseModel):
    role: Literal["customer", "assistant"]
    text: TurnText


class OrderAssistantState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["home", "menu", "options", "review", "supplies", "payment", "confirm", "cancel_confirmation"]
    category: str = Field(min_length=1, max_length=80)
    dining: Literal["매장 이용", "포장"] | None
    cart: list[dict] = Field(max_length=250)
    options: dict | None
    pending: dict | None
    rule_draft: dict | None
    checkout: dict | None


class OrderAssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    transcript: TurnText
    history: list[HistoryEntry] = Field(max_length=8)
    state: OrderAssistantState
    catalog: list[dict] = Field(max_length=250)
    categories: list[str] = Field(max_length=40)


@router.post("/turn")
def assistant_turn(turn: OrderAssistantTurn) -> dict:
    """Ask GPT for an order plan; the kiosk validates and applies allowed actions."""
    state = turn.state.model_dump()
    history = [entry.model_dump() for entry in turn.history]
    evidence = OrderEvidence.from_storage().select(turn.transcript, history, state)
    result = {"version": turn.version, "mode": "decision"}
    action = local_information_action(turn.transcript, evidence, turn.categories, state)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        from .main import get_menus  # Use the same authoritative catalog as the kiosk.

        catalog = get_menus()["items"]
        by_id = {item["id"]: item for item in catalog}
        categories = {"전체"} | {category for item in catalog for category in item.get("categories", [])}
        options = {}
        menu_rows = []
        for item in catalog:
            option_ids = []
            for group in item.get("option_groups", []):
                for choice in group["choices"]:
                    options[choice["id"]] = choice["label"]
                    option_ids.append(choice["id"])
            menu_rows.append([item["id"], item["name"], item.get("temperature"), option_ids])

        try:
            actions = decide_order(key, {
                "transcript": turn.transcript, "history": history, "state": state,
                "categories": sorted(categories), "menu_fields": ["menu_id", "name", "temperature", "option_ids"],
                "menus": menu_rows, "option_labels": options,
                "matched_menu_ids": [item["menu_id"] for item in evidence["menus"]],
                "registered_information_available": action is not None,
            })
            validate_plan(actions, by_id, categories)
        except OrderProviderError:
            return {**result, "source": "unavailable", "actions": [
                {"type": "inform", "text": "지금 음성 주문을 처리하지 못했어요. 다시 말씀하시거나 화면에서 골라 주세요."},
            ]}
        if actions[0]["type"] == "answer_information":
            actions = [action or {"type": "inform", "text": "등록된 정보에서 확인하지 못했어요. 직원에게 문의해 주세요."}]
        elif actions[0]["type"] == "cannot_help":
            actions = [{"type": "inform", "text": "주문 내용을 다시 말씀하시거나 화면에서 선택해 주세요."}]
        return {**result, "source": "openai", "actions": actions}
    if action:
        return {**result, "source": "local_information", "actions": [action], "evidence": evidence}
    return {"version": turn.version, "mode": "rules", "evidence": evidence}


def validate_plan(actions, catalog, categories):
    terminal = {"ask", "open_checkout", "request_cancel", "answer_information", "cannot_help"}
    for index, action in enumerate(actions):
        kind = action["type"]
        if (kind in terminal and index != len(actions) - 1
                or kind in {"answer_information", "cannot_help"} and len(actions) != 1):
            raise OrderProviderError("invalid_sequence")
        if kind == "show_category" and action["category"] not in categories:
            raise OrderProviderError("invalid_category")
        if kind == "ask" and any(item_id not in catalog for item in action["items"] for item_id in item["menu_ids"]):
            raise OrderProviderError("invalid_pending_item")
        if kind == "add_items":
            for line in action["items"]:
                item = catalog.get(line["menu_id"])
                if item is None:
                    raise OrderProviderError("invalid_menu")
                groups = {choice["id"]: group["id"] for group in item.get("option_groups", []) for choice in group["choices"]}
                ids = line["option_ids"]
                if any(key not in groups for key in ids) or len({groups[key] for key in ids}) != len(ids):
                    raise OrderProviderError("invalid_options")
