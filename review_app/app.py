from __future__ import annotations

import sqlite3
import streamlit as st

from store import ACTIONS, approved_jsonl, get_reviews, load_questions, save_review

st.set_page_config(
    page_title="CAIFE 질문 살펴보기",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
    .stApp { background: #f6f8f5; color: #26392f; }
    .block-container { max-width: 1100px; padding: 1.5rem 2.5rem 4rem; }
    h1, h2, h3 { color: #183c2b !important; letter-spacing: -.03em; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid #e3ebe3;
        border-radius: 12px; padding: 14px 20px; }
    [data-testid="stMetricValue"] { color: #22533a; font-weight: 700; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: #dfe8df; }
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        min-height: 44px; border-radius: 8px; font-weight: 650;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: #24583c; border-color: #24583c;
    }
    [data-testid="stAlert"] { border-radius: 9px; }
    </style>
    """,
    unsafe_allow_html=True,
)

rows, missing, errors = load_questions()
try:
    reviews = get_reviews()
except (OSError, sqlite3.Error) as exc:
    st.error(f"저장된 평가를 불러오지 못했어요: {exc}")
    st.stop()

st.caption("CAIFE  /  질문 살펴보기")
st.title("질문 살펴보기")
st.write("질문과 키오스크의 처리 방법을 보고 괜찮은지 평가해 주세요.")
st.caption("지금 보이는 질문은 미리 만든 예시예요. AI 자동 생성과 검토는 아직 연결되지 않았어요.")

if missing or errors:
    with st.expander("불러오지 못한 자료 확인"):
        if missing:
            st.write(f"질문 파일 {len(missing)}개를 찾지 못했어요.")
            for path in missing:
                st.code(path)
        if errors:
            st.write(f"읽지 못한 항목이 {len(errors)}개 있어요.")
            st.write(errors)
if not rows:
    st.warning("아직 볼 수 있는 질문이 없어요. 질문 데이터가 있는지 확인해 주세요.")
    st.stop()

counts = {
    status: sum(1 for row in rows if reviews.get(row["key"], {}).get("status") == status)
    for status in ("승인", "수정 필요", "반려")
}
done = sum(counts.values())
st.write(f"전체 질문 {len(rows)}개  ·  평가 완료 {done}개  ·  남은 질문 {len(rows) - done}개")

with st.expander("질문 찾기 · 전체 목록 보기"):
    st.caption("검색하거나 원하는 질문을 목록에서 골라 볼 수 있어요.")
    search_column, status_column = st.columns([2, 1])
    with search_column:
        search = st.text_input("질문 검색", placeholder="예: 아메리카노, 화장실")
    with status_column:
        status_filter = st.selectbox(
            "평가 상태",
            ["전체", "아직 평가 안 함", "승인", "수정 필요", "반려"],
        )
    cat_col, data_col = st.columns(2)
    with cat_col:
        category = st.selectbox("질문 종류", ["전체"] + sorted({r["category"] for r in rows}))
    with data_col:
        dataset = st.selectbox("자료 종류", ["전체"] + sorted({r["dataset"] for r in rows}))

    def matches(row):
        state = reviews.get(row["key"], {}).get("status", "아직 평가 안 함")
        return (
            (not search or search.casefold() in row["question"].casefold()
             or search.casefold() in reviews.get(row["key"], {}).get("question", "").casefold())
            and (status_filter == "전체" or status_filter == state)
            and (category == "전체" or category == row["category"])
            and (dataset == "전체" or dataset == row["dataset"])
        )

    filtered = [row for row in rows if matches(row)]
    # Show usable examples first, while keeping holdout examples last.
    filtered.sort(key=lambda row: (
        2 if row["split"] in ("test", "holdout")
        else 0 if row["actions"] else 1
    ))
    st.caption(f"조건에 맞는 질문 {len(filtered)}개")

    if filtered:
        page_size = 25
        pages = (len(filtered) + page_size - 1) // page_size
        page = st.number_input("목록 페이지", min_value=1, max_value=pages, value=1, step=1)
        current_page = filtered[(page - 1) * page_size : page * page_size]
        st.dataframe(
            [{
                "질문": reviews.get(row["key"], {}).get("question", row["question"]),
                "처리 방법": (
                    reviews[row["key"]]["expected_action"] if row["key"] in reviews
                    else " · ".join(ACTIONS.get(a, a) for a in row["actions"])
                ) or "아직 없음",
                "평가": reviews.get(row["key"], {}).get("status", "아직 안 함"),
            } for row in current_page],
            hide_index=True,
            use_container_width=True,
        )
        st.caption(f"{page} / {pages} 페이지 · 한 페이지에 최대 25개")

        keys = [row["key"] for row in filtered]
        choices = {row["key"]: row for row in filtered}
        if st.session_state.get("selected_question") not in choices:
            # Prefer an existing action so the first question is immediately reviewable.
            # Avoid revealing held-out questions when a development example is available.
            st.session_state["selected_question"] = next(
                (r["key"] for r in filtered
                 if r["actions"] and r["split"] not in ("test", "holdout")
                 and r["key"] not in reviews),
                keys[0],
            )
        st.selectbox(
            "살펴볼 질문 선택",
            keys,
            format_func=lambda key: reviews.get(key, {}).get("question", choices[key]["question"]),
            key="selected_question",
        )

if not filtered:
    st.warning("조건에 맞는 질문이 없어요. 검색어나 평가 상태를 바꿔 주세요.")
    st.stop()

# The selector remains the source of truth for both search and next/previous.
selected_key = st.session_state["selected_question"]
item = choices[selected_key]
review = reviews.get(selected_key, {})
position = keys.index(selected_key)
shown_question = review.get("question", item["question"])
original_action = "\n".join(ACTIONS.get(a, a) for a in item["actions"])
shown_action = review["expected_action"] if review else original_action


def move_question(step, question_keys):
    current = st.session_state.get("selected_question")
    index = question_keys.index(current) if current in question_keys else 0
    index = max(0, min(len(question_keys) - 1, index + step))
    st.session_state["selected_question"] = question_keys[index]


st.divider()
header_col, navigation_col = st.columns([2, 1])
with header_col:
    st.subheader("이 질문을 살펴봐 주세요")
    st.caption(f"{position + 1} / {len(filtered)}번째 질문  ·  {item['category']}")
with navigation_col:
    previous, following = st.columns(2)
    previous.button(
        "← 이전", disabled=position == 0, on_click=move_question,
        args=(-1, keys), use_container_width=True,
    )
    following.button(
        "다음 →", disabled=position == len(keys) - 1, on_click=move_question,
        args=(1, keys), use_container_width=True,
    )

with st.container(border=True):
    st.caption("손님이 이렇게 말했어요")
    st.subheader(shown_question)
    if review:
        st.caption(f"내 평가: {review['status']}")
    else:
        st.caption("아직 평가하지 않은 질문이에요.")

    st.markdown("**키오스크는 어떻게 하면 될까요?**")
    if shown_action:
        for action in shown_action.splitlines():
            st.write("• " + action)
        st.caption("위 내용은 저장된 처리 방법이에요. AI가 실제로 실행한 결과는 아니에요.")
    else:
        st.write("아직 작성된 처리 방법이 없어요. 아래에 직접 적거나 수정 필요로 표시할 수 있어요.")

    if review and (shown_question != item["question"] or shown_action != original_action):
        with st.expander("처음 작성된 내용 보기"):
            st.write("처음 질문: " + item["question"])
            st.write("처음 처리 방법: " + (original_action or "없음"))

    if item["split"] != "train":
        st.warning("모델을 나중에 시험하기 위해 따로 둔 질문이에요. 이 질문은 학습용 파일에 포함되지 않아요.")

    if item["history"] or item["state"] or item["slots"]:
        with st.expander("앞선 대화와 주문 상황 보기"):
            if item["history"]:
                for turn in item["history"]:
                    st.write(f"{'손님' if turn.get('role') == 'user' else '안내'}: {turn.get('text', '')}")
            if item["state"]:
                st.write("현재 주문 상황")
                st.json(item["state"], expanded=False)
            if item["slots"]:
                st.write("알려진 주문 정보")
                st.json(item["slots"], expanded=False)

st.markdown("### 내 평가")
st.write("질문과 처리 방법을 읽고 선택해 주세요.")
default_action = original_action
decision_labels = ["괜찮아요", "수정이 필요해요", "사용하지 않을래요"]
decision_to_status = {
    "괜찮아요": "승인",
    "수정이 필요해요": "수정 필요",
    "사용하지 않을래요": "반려",
}
status_to_decision = {value: key for key, value in decision_to_status.items()}
existing_decision = status_to_decision.get(review.get("status"))

if "review_saved_message" in st.session_state:
    st.success(st.session_state.pop("review_saved_message"))

with st.form(key=f"review:{selected_key}"):
    decision = st.radio(
        "이 질문과 처리 방법이 적절한가요?",
        decision_labels,
        index=decision_labels.index(existing_decision) if existing_decision else None,
        horizontal=True,
    )
    with st.expander(
        "질문이나 처리 방법 수정하기",
        expanded=not bool(review.get("expected_action", default_action)),
    ):
        edited_question = st.text_area(
            "질문", value=review.get("question", item["question"]), height=85,
            help="질문을 고치고 싶다면 이곳에서 수정해 주세요.",
        )
        action = st.text_area(
            "키오스크가 할 일", value=review.get("expected_action", default_action),
            placeholder="예: 화장실 위치를 찾아서 안내해요.", height=100,
            help="괜찮아요로 저장하려면 키오스크가 할 일을 적어 주세요.",
        )
        answer = st.text_area(
            "손님에게 할 말", value=review.get("expected_answer", ""),
            placeholder="예: 화장실은 정문 밖 오른쪽 건물 2층에 있어요.", height=85,
        )
        comment = st.text_area(
            "남길 의견", value=review.get("comment", ""),
            placeholder="수정할 부분이나 평가한 이유를 적어 주세요. (선택)", height=85,
        )
    submitted = st.form_submit_button("평가 저장하기", type="primary", use_container_width=True)

if submitted:
    if decision is None:
        st.error("먼저 평가를 선택해 주세요.")
    else:
        try:
            save_review(selected_key, decision_to_status[decision], edited_question, action, answer, comment)
            st.session_state["review_saved_message"] = "평가를 저장했어요. 다음 질문도 살펴볼 수 있어요."
            st.rerun()
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(f"저장하지 못했어요: {exc}")

st.divider()
with st.expander("평가한 학습 자료 내려받기"):
    export = approved_jsonl(rows, reviews)
    export_count = len(export.splitlines())
    st.write(f"괜찮다고 평가한 학습용 질문 {export_count}개를 내려받을 수 있어요.")
    st.caption("시험·검증용 질문은 학습용 파일에서 제외돼요.")
    st.download_button(
        "학습 자료 내려받기",
        export.encode("utf-8"),
        file_name="caife_approved_train.jsonl",
        mime="application/x-ndjson",
        disabled=not export_count,
    )

with st.expander("AI 담당 업무 안내"):
    st.write("질문 생성 담당 → 질문을 만드는 역할")
    st.write("처리 방법 담당 → 질문에 맞는 행동과 답변을 정하는 역할")
    st.write("총괄 검토 담당 → 질문과 처리 방법을 점검하는 역할")
    st.write("최종 평가 → 직접 확인하고 승인하거나 수정하는 역할")
    st.caption("질문 생성·처리 방법·총괄 검토 AI는 아직 연결되지 않았어요.")

