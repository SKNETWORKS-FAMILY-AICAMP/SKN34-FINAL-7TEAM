from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .assistant_evidence import OrderEvidence, local_information_action

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
    """Retrieve local evidence and answer supported information requests before provider integration."""
    state = turn.state.model_dump()
    evidence = OrderEvidence.from_storage().select(turn.transcript, [entry.model_dump() for entry in turn.history], state)
    action = local_information_action(turn.transcript, evidence, turn.categories, state)
    if action:
        return {"version": turn.version, "mode": "decision", "actions": [action], "evidence": evidence}
    return {"version": turn.version, "mode": "rules", "evidence": evidence}
