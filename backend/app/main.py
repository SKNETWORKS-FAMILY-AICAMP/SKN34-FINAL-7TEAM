import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="CAIFE API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Confirm that the backend is reachable from the kiosk UI."""
    return {"status": "ok", "service": "CAIFE API"}


def menu_data_file() -> Path:
    default = Path(__file__).resolve().parents[2] / "data" / "menus" / "mega" / "mega_menu.json"
    return Path(os.environ.get("CAIFE_MENU_DATA_FILE", str(default)))


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
        "items": items,
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
