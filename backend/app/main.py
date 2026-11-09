import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

app = FastAPI(title="CAIFE API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Confirm that the backend is reachable from the kiosk UI."""
    return {"status": "ok", "service": "CAIFE API"}


def menu_data_file() -> Path:
    default = Path(__file__).resolve().parents[2] / "data" / "menus" / "mega" / "mega_menu.json"
    return Path(os.environ.get("CAIFE_MENU_DATA_FILE", str(default)))


# CAIFE initial common option policy, using prices from the supplied reference image.
# It is a project configuration, not a verified per-menu franchise option list.
DRINK_OPTION_GROUPS = [
    {"id": "tumbler", "label": "텀블러 선택", "choices": [
        {"id": "tumbler", "label": "텀블러 사용", "price": 0},
    ]},
    {"id": "shot", "label": "샷 선택", "choices": [
        {"id": "shot_light", "label": "연하게", "price": 0},
        {"id": "shot_1", "label": "샷 1개 추가", "price": 600},
        {"id": "shot_2", "label": "샷 2개 추가", "price": 1200},
    ]},
    {"id": "sweet", "label": "당도 선택", "choices": [
        {"id": "stevia", "label": "저당 스테비아 추가", "price": 600},
        {"id": "condensed_milk", "label": "연유 추가", "price": 700},
    ]},
    {"id": "topping", "label": "토핑 선택", "choices": [
        {"id": "whipped_cream", "label": "휘핑 추가", "price": 500},
    ]},
]


def option_groups_for(item: dict) -> list:
    if item.get("group") != "음료":
        return []
    categories = item.get("categories")
    is_coffee = (
        isinstance(categories, list) and any(category in ("커피", "디카페인") for category in categories)
    ) or "커피" in str(item.get("name", ""))
    return [group for group in DRINK_OPTION_GROUPS if group["id"] != "shot" or is_coffee]


def public_menu_item(item: dict) -> dict:
    # Do not trust option definitions embedded in a separately supplied menu file.
    result = {key: value for key, value in item.items() if key != "option_groups"}
    groups = option_groups_for(item)
    if groups or item.get("group") == "푸드":
        result["option_groups"] = groups
    return result


@app.get("/api/menus")
def get_menus() -> dict:
    """Return locally collected menu data; never substitute demonstration data."""
    data_file = menu_data_file()
    try:
        with data_file.open(encoding="utf-8") as source_file:
            items = json.load(source_file)
        if not isinstance(items, list) or not items or any(
            not isinstance(item, dict) or not item.get("id") or not item.get("name")
            for item in items
        ):
            raise ValueError("invalid menu data")
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(
            status_code=503,
            detail="메뉴 데이터를 불러오지 못했어요. 데이터 파일을 확인해 주세요.",
        ) from None

    return {
        "items": [public_menu_item(item) for item in items],
        "collected_at": items[0].get("collected_at"),
        "source": items[0].get("source_url"),
    }


@app.get("/api/menu-images/{menu_id}")
def get_menu_image(menu_id: str) -> FileResponse:
    """Serve only locally downloaded images listed under a known menu ID."""
    missing = HTTPException(status_code=404, detail="이미지 정보가 없어요.")
    if not re.fullmatch(r"[0-9a-f]{20}", menu_id):
        raise missing
    images = menu_data_file().parent / "images"
    try:
        with (images / "index.json").open(encoding="utf-8") as index_file:
            index = json.load(index_file)
        filename = index.get(menu_id) if isinstance(index, dict) else None
        if not isinstance(filename, str) or filename not in {
            f"{menu_id}.png", f"{menu_id}.jpg", f"{menu_id}.webp", f"{menu_id}.gif"
        }:
            raise missing
        image = images / filename
        if not image.is_file() or image.is_symlink():
            raise missing
    except (OSError, UnicodeError, ValueError):
        raise missing from None
    return FileResponse(image, headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    menu_id: str = Field(min_length=1, max_length=100)
    quantity: StrictInt = Field(ge=1, le=99)
    options: list[str] = Field(default_factory=list, max_length=4)


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    dining: Literal["매장 이용", "포장"]
    items: list[OrderItem] = Field(min_length=1, max_length=100)
    supplies: list[Literal["straw", "bag", "self"]] = Field(default_factory=list, max_length=3)
    payment_method: Literal["card", "easy"]
    expected_total: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def validate_items_and_supplies(self):
        lines = [(item.menu_id, tuple(sorted(item.options))) for item in self.items]
        if len(lines) != len(set(lines)):
            raise ValueError("같은 메뉴와 옵션은 수량을 합쳐서 보내 주세요.")
        if len(self.supplies) != len(set(self.supplies)) or (
            "self" in self.supplies and len(self.supplies) > 1
        ):
            raise ValueError("일회용품 선택을 확인해 주세요.")
        return self


def order_database_file() -> Path:
    default = Path(__file__).resolve().parents[2] / "data" / "orders" / "caife.sqlite3"
    return Path(os.environ.get("CAIFE_ORDER_DB_FILE", str(default)))


@app.post("/api/orders")
def create_order(order: OrderRequest) -> dict:
    """Persist a local unpaid order; this does not process payment or notify a store."""
    payload = order.model_dump(mode="json")
    fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    db_file = order_database_file()
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(db_file, timeout=10)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS orders (
                request_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                result TEXT NOT NULL
            )""")
            # Serialize the check and insertion so simultaneous retries cannot duplicate an order.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload, result FROM orders WHERE request_id = ?", (str(order.request_id),)
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise HTTPException(status_code=409, detail="이미 사용한 주문 요청 번호입니다.")
                return json.loads(existing[1])

            menu_items = get_menus()["items"]
            by_id = {item["id"]: item for item in menu_items}
            if len(by_id) != len(menu_items):
                raise HTTPException(status_code=503, detail="메뉴 정보를 확인할 수 없어요.")
            lines = []
            for requested in order.items:
                item = by_id.get(requested.menu_id)
                if not item:
                    raise HTTPException(status_code=400, detail="선택한 메뉴를 찾을 수 없어요.")
                price = item.get("price")
                if type(price) is not int or price < 0:
                    raise HTTPException(status_code=400, detail="선택한 메뉴의 가격을 확인할 수 없어요.")
                choices = {}
                for group in option_groups_for(item):
                    for choice in group["choices"]:
                        choices[choice["id"]] = (group["id"], choice)
                selected_groups = set()
                selected_options = []
                for option_id in requested.options:
                    entry = choices.get(option_id)
                    if not entry or entry[0] in selected_groups:
                        raise HTTPException(status_code=400, detail="선택할 수 없는 옵션입니다.")
                    group_id, choice = entry
                    selected_groups.add(group_id)
                    selected_options.append({"id": choice["id"], "label": choice["label"], "price": choice["price"]})
                unit_price = price + sum(option["price"] for option in selected_options)
                lines.append({"menu_id": requested.menu_id, "name": item["name"],
                              "quantity": requested.quantity, "base_price": price,
                              "selected_options": selected_options, "unit_price": unit_price,
                              "line_total": unit_price * requested.quantity})
            total = sum(item["line_total"] for item in lines)
            if order.expected_total != total:
                raise HTTPException(status_code=409, detail="메뉴 가격이 변경됐어요. 주문 금액을 다시 확인해 주세요.")

            result = {"order_id": str(uuid4()), "request_id": str(order.request_id),
                      "created_at": datetime.now(timezone.utc).isoformat(), "dining": order.dining,
                      "supplies": order.supplies, "payment_method": order.payment_method,
                      "items": lines, "total": total, "status": "recorded", "payment_status": "unpaid"}
            connection.execute("INSERT INTO orders (request_id, payload, result) VALUES (?, ?, ?)",
                               (str(order.request_id), fingerprint, json.dumps(result, ensure_ascii=False)))
            return result
    except (OSError, sqlite3.Error):
        raise HTTPException(status_code=503, detail="주문을 저장하지 못했어요. 다시 시도해 주세요.") from None
