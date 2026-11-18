from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from store import ACTIONS, approved_jsonl, connect, get_reviews, load_questions, save_review

static_dir = Path(__file__).with_name("static")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


class Evaluation(BaseModel):
    status: Literal["승인", "수정 필요", "반려"]
    question: str = Field(max_length=4000)
    action: str = Field(default="", max_length=8000)
    answer: str = Field(default="", max_length=8000)
    comment: str = Field(default="", max_length=8000)


@app.get("/")
def home():
    return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/review")
def review_data():
    try:
        rows, missing, errors = load_questions()
        reviews = get_reviews()
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "검토 자료를 불러오지 못했습니다.") from None
    questions = [
        {
            "id": row["key"],
            "question": row["question"],
            "category": row["category"],
            "dataset": row["dataset"],
            "split": row["split"],
            "actions": [ACTIONS.get(value, value) for value in row["actions"]],
            "history": row["history"],
            "review": reviews.get(row["key"]),
        }
        for row in rows
    ]
    return {"questions": questions, "source_issues": len(missing) + len(errors)}


@app.put("/api/review/evaluation")
def update_evaluation(question_id: str, evaluation: Evaluation):
    try:
        rows, _, _ = load_questions()
        if not any(row["key"] == question_id for row in rows):
            raise HTTPException(404, "질문을 찾을 수 없습니다.")
        save_review(
            question_id, evaluation.status, evaluation.question,
            evaluation.action, evaluation.answer, evaluation.comment,
        )
        return get_reviews()[question_id]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "평가를 저장하지 못했습니다.") from None


@app.get("/api/review/approved.jsonl")
def download_approved():
    try:
        rows, _, _ = load_questions()
        data = approved_jsonl(rows, get_reviews())
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "평가 자료를 준비하지 못했습니다.") from None
    return Response(
        data, media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="caife_approved_train.jsonl"'},
    )


@app.get("/api/review/usage")
def usage():
    try:
        with closing(connect()) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS review_gpt_usage (
                response_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('question_generator', 'action_generator', 'supervisor')),
                input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0),
                output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0),
                total_tokens INTEGER NOT NULL CHECK(total_tokens >= 0),
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            records = con.execute("""
                SELECT role, COUNT(*) AS calls, SUM(input_tokens) AS input,
                       SUM(output_tokens) AS output, SUM(total_tokens) AS total
                FROM review_gpt_usage GROUP BY role
            """).fetchall()
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "GPT 사용량을 불러오지 못했습니다.") from None
    return {
        "roles": [dict(record) for record in records],
        "calls": sum(record["calls"] for record in records),
        "total": sum(record["total"] for record in records),
    }
