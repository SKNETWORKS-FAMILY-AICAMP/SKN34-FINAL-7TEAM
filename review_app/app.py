from __future__ import annotations

import json
import sqlite3
import streamlit as st
from store import ACTIONS, approved_jsonl, get_reviews, load_questions, save_review

st.set_page_config(page_title='CAIFE 데이터 검토실', page_icon='☕', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp {background: #f5f7f5; color: #1c3027;}
[data-testid="stSidebar"] {background: #173d2d;}
[data-testid="stSidebar"] * {color: #fff !important;}
[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {color: #20372c !important;}
.block-container {max-width: 1440px; padding: 2rem 3rem;}
h1, h2, h3 {color: #173d2d !important; letter-spacing: -.035em;}
[data-testid="stMetric"] {background: white; border: 1px solid #e0e9e2; border-radius: 10px; padding: 16px 20px;}
[data-testid="stMetricLabel"] {font-size: .95rem;}
[data-testid="stMetricValue"] {font-weight: 700; color: #23543a;}
.stButton > button, .stDownloadButton > button {border-radius: 8px; min-height: 45px; font-weight: 650;}
.stButton > button[kind="primary"] {background: #23543a; border: 1px solid #23543a;}
[data-testid="stAlert"] {border-radius: 8px;}
</style>''', unsafe_allow_html=True)

rows, missing, errors = load_questions()
try:
    reviews = get_reviews()
except Exception as exc:
    st.error(f'검토 저장소를 열 수 없습니다: {exc}')
    st.stop()

with st.sidebar:
    st.markdown('## CAIFE')
    st.caption('DATA OPERATIONS')
    st.markdown('---')
    st.markdown('### 질문 검토실')
    st.write('주문 데이터를 검토하고 최종 결과를 저장합니다.')
    st.markdown('---')
    st.markdown('**담당 업무**')
    st.markdown('① 질문 생성 담당  ·  연결 전')
    st.markdown('② 행동 생성 담당  ·  연결 전')
    st.markdown('③ 총괄 검토 담당  ·  연결 전')
    st.markdown('④ 최종 평가  ·  사용자')
    st.markdown('---')
    st.caption('질문 자동 생성 및 정기 실행은 AI API 연결 후 구현합니다.')

st.caption('CAIFE / 데이터 관리 / 질문 검토실')
st.title('질문 검토실')
st.write('현재 준비된 질문과 예상 행동을 살펴보고 직접 평가해 주세요.')
st.info('기존 질문은 직접 작성한 합성 문장입니다. 아직 AI가 답변이나 검토 결과를 생성하지 않았습니다.')

if missing:
    with st.expander(f'불러오지 못한 데이터 파일 {len(missing)}개'):
        st.write('전처리 결과 파일이 있으면 자동으로 표시됩니다.')
        for path in missing:
            st.code(path)
if errors:
    with st.expander(f'읽지 못한 데이터 행 {len(errors)}개'):
        st.write(errors)
if not rows:
    st.warning('표시할 질문이 없습니다. 전처리 결과 파일을 준비해 주세요.')
    st.stop()

counts = {status: sum(1 for r in rows if reviews.get(r['key'], {}).get('status') == status) for status in ('승인', '수정 필요', '반려')}
cols = st.columns(5)
for column, label, value in zip(cols, ['전체 질문', '검토 전', '승인', '수정 필요', '반려'],
                                 [len(rows), len(rows) - sum(counts.values()), counts['승인'], counts['수정 필요'], counts['반려']]):
    column.metric(label, value)

st.divider()
st.subheader('질문 목록')
a, b, c, d = st.columns([2, 1.1, 1.1, 1.1])
with a:
    search = st.text_input('질문 검색', placeholder='메뉴명이나 질문을 입력하세요')
with b:
    datasets = ['전체'] + sorted({r['dataset'] for r in rows})
    dataset = st.selectbox('데이터 종류', datasets)
with c:
    categories = ['전체'] + sorted({r['category'] for r in rows})
    category = st.selectbox('질문 유형', categories)
with d:
    status = st.selectbox('검토 상태', ['전체', '검토 전', '승인', '수정 필요', '반려'])

filtered = [r for r in rows
    if (not search or search.casefold() in r['question'].casefold())
    and (dataset == '전체' or dataset == r['dataset'])
    and (category == '전체' or category == r['category'])
    and (status == '전체' or status == reviews.get(r['key'], {}).get('status', '검토 전'))]
st.caption(f'조건에 맞는 질문 {len(filtered)}건')
if not filtered:
    st.warning('조건에 맞는 질문이 없습니다.')
    st.stop()

page_size = 25
page_count = (len(filtered) + page_size - 1) // page_size
page = st.number_input('목록 페이지', min_value=1, max_value=page_count, value=1, step=1)
page_rows = filtered[(page - 1) * page_size : page * page_size]
st.dataframe([{
    '질문': r['question'], '유형': r['category'],
    '기존 예상 행동': ' · '.join(ACTIONS.get(a, a) for a in r['actions']) or '없음',
    '검토 상태': reviews.get(r['key'], {}).get('status', '검토 전'),
    '분할': r['split'],
} for r in page_rows], hide_index=True, use_container_width=True)
st.caption(f'{page} / {page_count} 페이지 · 한 페이지당 최대 {page_size}건')

# The selection presents actual utterances, rather than opaque generated IDs.
choices = {r['key']: r for r in filtered}
selected_key = st.selectbox('검토할 질문 선택', list(choices),
    format_func=lambda key: f"[{reviews.get(key, {}).get('status', '검토 전')}] {choices[key]['question']}  ·  {choices[key]['category']}")
item = choices[selected_key]
review = reviews.get(selected_key, {})

left, right = st.columns([1.05, 1], gap='large')
with left:
    st.markdown('### 질문 상세')
    st.markdown(f"**질문**  \n{item['question']}")
    st.write(f"**유형:** {item['category']}　 |　 **데이터:** {item['dataset']}")
    st.write(f"**원본 분할:** {item['split']}　 |　 **문장 그룹:** {item['group_id']}")
    if item['intent']:
        st.write(f"**기존 의도:** {item['intent']}")
    st.caption(f"출처: {item['source']}")
    if item['split'] != 'train':
        st.warning('검증·시험·보류용 질문입니다. 이 문항을 열람하거나 수정하면 독립적인 최종 평가에 영향을 줄 수 있습니다. 학습용 내보내기에는 포함되지 않습니다.')
    if item['actions']:
        st.markdown('**기존에 작성된 예상 행동**')
        for action in item['actions']:
            st.write('• ' + ACTIONS.get(action, action))
    else:
        st.caption('기존 예상 행동 없음 · 사용자가 작성할 수 있습니다.')
    st.caption('기존 예상 행동은 설계 초안이며 AI의 실제 실행 결과가 아닙니다.')
    if item['slots']:
        st.markdown('**기존에 지정한 주문 정보**')
        st.json(item['slots'], expanded=True)
    if item['history'] or item['state']:
        with st.expander('앞선 대화와 현재 주문 상황'):
            if item['history']:
                st.write('앞선 대화')
                for turn in item['history']:
                    st.write(f"{'고객' if turn.get('role') == 'user' else '안내'}: {turn.get('text', '')}")
            if item['state']:
                st.write('현재 상황')
                st.json(item['state'], expanded=True)
    st.markdown('**행동 담당 AI**　연결 전')
    st.markdown('**총괄 검토 AI**　연결 전')

with right:
    st.markdown('### 최종 평가')
    st.caption('질문과 예상 행동을 직접 수정하고 결과를 저장해 주세요.')
    default_action = '\n'.join(ACTIONS.get(a, a) for a in item['actions'])
    with st.form(key=f'review:{selected_key}'):
        edited_question = st.text_area('질문', value=review.get('question', item['question']), height=100)
        action = st.text_area('예상 행동', value=review.get('expected_action', default_action),
                              placeholder='예: 메뉴를 확인하고 필요한 옵션을 질문합니다.', height=110)
        answer = st.text_area('예상 안내 문구', value=review.get('expected_answer', ''),
                              placeholder='예: 어떤 온도로 드릴까요? (필요한 경우 입력)', height=100)
        comment = st.text_area('검토 의견', value=review.get('comment', ''), placeholder='수정 이유나 판단 근거를 남겨 주세요.', height=90)
        decision = st.radio('최종 평가', ['승인', '수정 필요', '반려'],
                            index=['승인', '수정 필요', '반려'].index(review.get('status', '승인')), horizontal=True)
        submitted = st.form_submit_button('평가 저장', type='primary', use_container_width=True)
    if submitted:
        try:
            save_review(selected_key, decision, edited_question, action, answer, comment)
            st.success('평가를 저장했습니다.')
            st.rerun()
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(f'저장하지 못했습니다: {exc}')

st.divider()
export = approved_jsonl(rows, reviews)
export_count = len(export.splitlines())
st.subheader('승인 데이터 내보내기')
st.caption(f'승인된 학습용(train) 질문 {export_count}건만 포함합니다. 검증·시험·보류 문항은 제외합니다.')
st.download_button('승인한 학습 데이터 내려받기', export.encode('utf-8'), file_name='caife_approved_train.jsonl', mime='application/x-ndjson', disabled=not export_count)

