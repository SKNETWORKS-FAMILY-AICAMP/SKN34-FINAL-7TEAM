from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(os.environ.get('CAIFE_PROJECT_ROOT', Path(__file__).resolve().parents[1]))
DB_PATH = Path(os.environ.get('CAIFE_REVIEW_DB', ROOT / 'review_data' / 'reviews.sqlite3'))

DATA_FILES = [
    *[(ROOT / 'data' / 'intents' / 'processed' / f'{split}.jsonl', '단일 의도') for split in ('train', 'validation', 'test')],
    (ROOT / 'data' / 'dialogue' / 'processed' / 'dialogue_multilabel_train.jsonl', '다중 의도 학습'),
    (ROOT / 'data' / 'dialogue' / 'processed' / 'dialogue_development.jsonl', '문맥 시나리오'),
    (ROOT / 'data' / 'dialogue' / 'processed' / 'dialogue_holdout.jsonl', '문맥 시나리오'),
]

ACTIONS = {
    'resolve_menu': '메뉴 확인', 'validate_required_options': '필수 옵션 확인',
    'add_if_complete': '정보가 갖춰지면 장바구니에 담기',
    'resolve_context_menu': '앞선 대화에서 메뉴 확인', 'lookup_menu_attribute': '메뉴 정보 조회',
    'do_not_infer_safety': '알레르기 안전 여부 추측하지 않기',
    'preserve_unit_and_basis': '단위와 기준량 함께 안내', 'lookup_store_info': '매장 정보 조회',
    'guide_customer_to_staff': '직원에게 문의하도록 안내', 'do_not_claim_staff_called': '직원 호출 완료로 안내하지 않기',
    'ask_clarification': '추가 질문하기', 'do_not_change_cart_before_clarification': '확인 전 장바구니 변경하지 않기',
    'check_store_info': '매장 정보 확인', 'do_not_claim_external_action': '실행하지 않은 외부 기능 완료로 안내하지 않기',
    'explain_unavailable': '지원하지 않는 기능 안내', 'change_screen_size': '화면 크게 표시',
    'change_cart_quantity': '장바구니 수량 변경', 'remove_cart_item': '장바구니에서 삭제', 'show_cart': '장바구니 보여주기',
}


def load_questions():
    """Read distinct datasets only; retain original split and stable identifier."""
    rows, missing, errors = [], [], []
    seen = set()
    for path, dataset in DATA_FILES:
        if not path.exists():
            missing.append(str(path))
            continue
        with path.open(encoding='utf-8-sig') as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    item_id = str(raw.get('scenario_id') or raw['id'])
                    key = f'{dataset}:{item_id}'
                    if key in seen:
                        raise ValueError('중복된 질문 ID')
                    seen.add(key)
                    rows.append({
                        'key': key, 'dataset': dataset, 'question': raw.get('utterance') or raw['text'],
                        'category': raw.get('category') or raw.get('intent', '미분류').replace('_', ' '),
                        'intent': ', '.join(raw.get('intents', [])) or raw.get('intent', ''),
                        'split': raw.get('split', ''), 'group_id': raw.get('group_id', ''),
                        'actions': raw.get('expected_actions', []), 'slots': raw.get('expected_slots', {}),
                        'history': raw.get('conversation_history', []), 'state': raw.get('current_state', {}),
                        'source': raw.get('source', '직접 작성한 합성 문장'), 'note': raw.get('note', ''),
                    })
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(f'{path.name}:{number}: {exc}')
    return rows, missing, errors


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('''CREATE TABLE IF NOT EXISTS reviews (
        question_key TEXT PRIMARY KEY, status TEXT NOT NULL, question TEXT NOT NULL,
        expected_action TEXT NOT NULL, expected_answer TEXT NOT NULL,
        comment TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS review_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question_key TEXT NOT NULL,
        status TEXT NOT NULL, question TEXT NOT NULL, expected_action TEXT NOT NULL,
        expected_answer TEXT NOT NULL, comment TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    con.commit()
    return con


def get_reviews():
    with closing(connect()) as con:
        return {row['question_key']: dict(row) for row in con.execute('SELECT * FROM reviews')}


def save_review(key, status, question, action, answer, comment):
    if status not in {'승인', '수정 필요', '반려'}:
        raise ValueError('유효하지 않은 검토 상태입니다.')
    question, action, answer, comment = (value.strip() for value in (question, action, answer, comment))
    if not question:
        raise ValueError('질문을 입력해 주세요.')
    if status == '승인' and not action:
        raise ValueError('승인하려면 예상 행동을 입력해 주세요.')
    with closing(connect()) as con:
        values = (key, status, question, action, answer, comment)
        con.execute('''INSERT INTO reviews (question_key,status,question,expected_action,expected_answer,comment)
          VALUES (?,?,?,?,?,?) ON CONFLICT(question_key) DO UPDATE SET
          status=excluded.status, question=excluded.question, expected_action=excluded.expected_action,
          expected_answer=excluded.expected_answer, comment=excluded.comment, updated_at=CURRENT_TIMESTAMP''', values)
        con.execute('INSERT INTO review_history (question_key,status,question,expected_action,expected_answer,comment) VALUES (?,?,?,?,?,?)', values)
        con.commit()


def approved_jsonl(rows, reviews):
    records = []
    for item in rows:
        review = reviews.get(item['key'])
        if not review or review['status'] != '승인' or item['split'] != 'train':
            continue
        records.append(json.dumps({
            'question_id': item['key'], 'question_original': item['question'],
            'question_approved': review['question'], 'expected_action': review['expected_action'],
            'expected_answer': review['expected_answer'], 'review_comment': review['comment'],
            'original_split': item['split'], 'group_id': item['group_id'],
            'intent': item.get('intent', ''), 'category': item.get('category', ''),
            'expected_actions_original': item.get('actions', []),
            'expected_slots': item.get('slots', {}), 'conversation_history': item.get('history', []),
            'current_state': item.get('state', {}),
            'source': item['source'], 'dataset': item['dataset'], 'reviewed_at_utc': review['updated_at'],
        }, ensure_ascii=False))
    return '\n'.join(records) + ('\n' if records else '')



