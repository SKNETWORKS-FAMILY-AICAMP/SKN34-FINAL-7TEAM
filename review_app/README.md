# CAIFE Review

키오스크와 분리된 로컬 검토 웹입니다. 질문·행동·평가·GPT 사용량을 탭으로 확인합니다.

기존 Compose에서 검토 서비스만 실행합니다.

```powershell
docker volume create caife-review_caife_review_data
docker compose up -d --build review
```

주소는 http://127.0.0.1:8501/ 입니다.

- 기존 질문 자료는 읽기 전용으로 가져옵니다. 사용자 평가와 이력은 기존 SQLite 볼륨에 기록합니다.
- 학습용·검증용·시험용 질문을 확인할 수 있습니다. 승인한 학습용 질문만 JSONL로 내려받습니다.
- 질문과 예상 행동은 기존 전처리 자료를 표시합니다. 사용자 평가 탭에서 저장한 판단과 의견을 확인할 수 있습니다.
- GPT 사용량 탭은 `review_gpt_usage`에 적재된 실제 호출 건수와 토큰을 역할별로 집계합니다. GPT 호출, 에이전트 실행 기록 적재, 토큰 기록은 후속 연동 범위입니다.
