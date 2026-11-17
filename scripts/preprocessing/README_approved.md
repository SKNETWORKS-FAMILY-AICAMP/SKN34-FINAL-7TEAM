# 승인한 질문을 학습 자료로 정리

검토 화면에서 승인한 **학습용 질문**을 형식이 통일된 전처리 초안과 결합합니다. 원본과 기존 결과 파일은 변경하지 않습니다.

## 준비

1. 검토 화면에서 학습용 질문을 살펴보고 처리 방법을 작성해 `괜찮아요`로 저장합니다.
2. 화면 하단에서 `학습 자료 내려받기`를 선택합니다.
3. 이전 버전에서 내려받은 파일은 승인 상태 정보가 없으므로, 개선된 화면에서 새로 내려받습니다.
4. `data/intents/processed/unified_v1`에 통일된 train, validation, test JSONL이 있어야 합니다.

승인할 질문이 없다면 결과가 만들어지지 않습니다.

## 실행 예시

프로젝트 루트에서 실행합니다. 아래 `approved.jsonl`은 사용자가 다운로드한 파일 경로로 바꿉니다. 결과 폴더는 존재하지 않는 새 폴더여야 합니다.

```powershell
python scripts/preprocessing/prepare_approved_training.py --unified-dir data/intents/processed/unified_v1 --approved-file "$env:USERPROFILE/Downloads/caife_approved_train.jsonl" --output-dir data/intents/processed/approved_v1
```

- `approved_all.jsonl`: 승인한 학습용 질문 전체. 원본 질문과 라벨, 검토 질문·처리 방법·안내 문구를 함께 보존합니다.
- `training_ready.jsonl`: 승인 후 질문 문장이 바뀌지 않은 자료입니다.
- `needs_label_review.jsonl`: 사용자가 질문 문장을 바꾼 자료입니다. 원래 의도 라벨이 여전히 맞는지 다시 검토할 때까지 학습용에서 제외합니다.
- `manifest.json`: 결과 수량, 입력 파일 해시와 한계입니다.

검토·시험 질문은 학습용으로 결합하지 않습니다. 승인 상태, 질문 ID, 원문, 그룹을 확인하고 중복된 질문이나 검증·시험 질문과 정확히 일치하는 문장을 거부합니다. 의미가 비슷한 문장까지 자동으로 걸러내지는 않습니다.

승인 상태 표시는 파일의 무결성을 보장하지 않습니다. 사용자가 CAIFE 검토 화면에서 직접 내려받은 신뢰할 수 있는 파일을 사용합니다. 이 과정은 모델 학습을 하지 않습니다.

