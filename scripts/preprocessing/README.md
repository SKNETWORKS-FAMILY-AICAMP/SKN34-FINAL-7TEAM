# CAIFE 데이터 전처리

메뉴 검색용 데이터와 주문 의도 분류 학습용 데이터를 각각 준비합니다. 아래 명령은 프로젝트 루트에서 실행합니다.

## 1. 실행 준비

메뉴 원본은 `data/menus/mega/mega_menu.json`에 있어야 합니다. Python 환경을 활성화한 후 문자 단위 TF-IDF 처리에 필요한 패키지를 설치합니다.

```bash
python -m pip install -r scripts/preprocessing/requirements.txt
```

## 2. 전처리 실행

### 메뉴 데이터 정리

```bash
python scripts/preprocessing/prepare_menus.py --input data/menus/mega/mega_menu.json --output-dir data/menus/mega/processed
```

- `menus.normalized.json`: ID, 이름, 온도, 가격, 출처와 원본을 보존한 메뉴 데이터
- `menus.search.json`: 메뉴 한 개를 하나의 검색 단위로 정리한 문서
- `menus.aliases.json`: 메뉴명과 별칭에 대응하는 모든 후보 메뉴 ID 및 충돌 여부
- `menus.stats.json`: 처리 건수, 결측값, 품질 플래그와 입력 원본 해시

메뉴명과 공백을 정리하고, 아이스·핫 아메리카노에만 검토된 온도 표현을 추가합니다. 같은 별칭에 여러 메뉴가 연결되면 후보를 모두 보존하므로 실제 주문 처리 시 사용자에게 구분하여 물어야 합니다. 원본 가격과 카페인, 옵션 정보가 비어 있으면 추측해 채우지 않습니다. 영양값의 단위가 의심되는 항목은 원본 품질 플래그를 유지합니다.

### 주문 의도 문장 준비

```bash
python scripts/preprocessing/prepare_intents.py --output-dir data/intents/processed
```

- `intents_all.csv`: 원문·정규화 문장·의도·그룹·출처·분할 정보
- `train.jsonl`, `validation.jsonl`, `test.jsonl`: 학습·검증·시험 문장
- `manifest.json`: 분할·중복 검사와 데이터 집계

이 데이터는 **직접 작성한 문장 틀을 조합한 합성 텍스트**입니다. 실제 고객 발화, 음성 녹음, STT 인식 결과가 아닙니다. 문장 틀을 먼저 분할한 뒤 틀별 변형을 만들어 그룹이 다른 분할에 섞이지 않도록 합니다. 문장 원형과 실제 사용자 다양성이 제한적이므로 이 데이터만으로 실사용 성능을 판단하지 않습니다.

### 문자 단위 TF-IDF 변환

```bash
python scripts/preprocessing/vectorize_intents.py --input-dir data/intents/processed --output-dir data/intents/processed
```

- `tfidf_vectorizer.joblib`: 학습 데이터로만 맞춘 문자 단위 TF-IDF 변환기
- `tfidf_train.npz`, `tfidf_validation.npz`, `tfidf_test.npz`: 각 데이터 분할을 숫자로 변환한 결과
- `manifest.json`: 특징 개수, 행렬 크기, 사용한 라이브러리 버전 등 기록

행렬의 행 순서는 해당 분할의 JSONL 순서와 같습니다. 변환기를 학습 데이터에만 맞춘 다음 같은 변환기로 검증·시험 데이터를 변환합니다. **이는 특징 변환을 준비한 단계이며 주문 의도 분류 모델 학습이나 메뉴 벡터DB 구축을 완료했다는 뜻은 아닙니다.**

## 3. 저장과 검증

- 메뉴 원본 및 파생 결과 `data/menus/mega/processed/`에는 제3자 메뉴 자료가 포함되므로 기존 원본과 같은 Git 제외 정책을 따릅니다.
- 합성 문장·행렬 결과는 `data/intents/processed/`에 저장하며 Git에서 제외합니다. 스크립트와 실행 방법을 보관하고 필요할 때 다시 생성합니다.
- 각 명령은 지정한 결과 폴더의 같은 이름 파일을 다시 생성합니다. 다른 결과를 보관하려면 별도 출력 폴더를 지정합니다.
- `.joblib` 파일은 신뢰할 수 있는 출처에서 생성한 것만 불러옵니다.
- 음성 입력, LLM 주문 처리, 벡터DB 적재 및 결제 연동은 이 스크립트에 포함되지 않습니다.

메뉴 정규화의 핵심 검증은 다음 명령으로 실행합니다.

```bash
python -m unittest discover -s scripts/preprocessing -p test_prepare_menus.py -v
```


## 4. 용량·영양·알레르기 정보 보강

메뉴 정규화 스크립트는 `menu_facts`에 용량과 열량·당류·카페인·나트륨·단백질·포화지방·알레르기를 구조화합니다. 단위, 기준량, 원문, 출처, 확인 상태를 함께 보존합니다. 컵 용량을 실제 음료량으로 가정하지 않습니다. 알레르기 정보의 미기재는 성분이 없다는 의미가 아닙니다. 공식 설명에 원료 전환 등 조건이 있거나 단위가 이상한 값은 원문을 보존하고 검토 대상으로 표시합니다.

기존 결과를 보존하고 보강 결과를 따로 만들려면 다음을 실행합니다.

```bash
python scripts/preprocessing/prepare_menus.py --input data/menus/mega/mega_menu.json --output-dir data/menus/mega/processed_v2
```

생성 자료는 제3자 원본에서 파생되므로 `data/menus/mega/`의 기존 Git 제외 규칙을 따릅니다. `menus.search.json`에는 원문과 확인 플래그가 함께 들어갑니다. 실제 답변 기능은 구조화된 필드와 상태·조건을 확인해 만들어야 하며, 검색 텍스트만으로 확답해서는 안 됩니다.

## 5. 가상 매장 정보

사용자가 제공한 시연용 화장실 위치, 남녀 동일 이용 정보, 따뜻한 물 안내, 영업시간은 로컬 `data/store/store.demo.json`에 저장합니다. 고객에게 안내할 값은 실제 매장의 민감한 운영정보로 대체하지 않습니다. 영업 요일과 휴무일은 아직 지정하지 않았습니다. 로컬 파일과 결과는 Git에 포함되지 않습니다.

다른 환경에서는 `scripts/preprocessing/store.example.json`을 참고하여 직접 로컬 입력 파일을 만든 다음 다음 명령을 실행합니다.

```bash
python scripts/preprocessing/prepare_store.py --input data/store/store.demo.json --output data/store/store.facts.json
```

## 6. 문맥·복합 요청 평가 시나리오

기존 단일 의도 576건과 TF-IDF 결과를 유지하면서, 영양·알레르기, 매장 안내, 따뜻한 물, 방언풍 텍스트, 문맥 참조, 복합 요청, 모호한 요청 등을 별도의 합성 시나리오로 만듭니다. 예상 행동은 실제 구현 완료를 의미하지 않습니다. 사투리 예시는 실제 지역 음성이나 STT 결과가 아닙니다.

```bash
python scripts/preprocessing/prepare_dialogue_scenarios.py --baseline-dir data/intents/processed --output-dir data/dialogue/processed
python scripts/preprocessing/prepare_multilabel_dialogue.py --baseline-dir data/intents/processed --output-dir data/dialogue/processed
```

`dialogue_scenarios_manifest.json`에 규모, 분할, 중복 검사와 한계가 기록됩니다. 개발용 문장과 보류용 문장은 각각 별도로 보관합니다. 표현이나 의미까지 완전히 독립적이라는 뜻은 아닙니다.

다중 의도 파일은 `dialogue_multilabel_train.jsonl`, `dialogue_multilabel_validation.jsonl`, `dialogue_multilabel_test.jsonl`입니다. 검증·시험 문장은 앞의 별도 평가 시나리오와 동일하므로 중복 합산하지 않습니다. 데이터는 합성 예시이며 학습 문장 수가 작아 실제 고객 성능을 대표하지 않습니다. 실제 분류 모델 학습 및 서비스 연결은 수행하지 않았습니다.

검증은 다음 명령으로 실행합니다.

```bash
python -m unittest discover -s scripts/preprocessing -p "test_*.py" -v
```

## 7. API 연결 전 질문 데이터 정리

기존 단일 의도와 문맥·복합 의도 자료의 이름과 형식을 통일합니다. 결과 폴더가 이미 있으면 덮어쓰지 않으므로 새 경로를 지정합니다.

```powershell
python scripts/preprocessing/prepare_unified_intents.py --project-root . --output-dir data/intents/processed/unified_v1
```

현재 자료의 결과는 672건이며 학습·검증·시험 순서로 320·176·176건입니다. 문장 원문, ID, 원래 라벨, 대화 맥락 및 분할을 보존합니다. 정확히 같은 문장과 같은 그룹의 분할 간 중복을 검사하지만, 의미가 비슷한 문장까지 독립이라는 뜻은 아닙니다. 결과는 사람 검토 전 합성 초안입니다.

질문 검토 화면에서 승인한 학습용 문항만 초안과 결합하는 절차는 [승인 질문 처리 안내](README_approved.md)를 참고하세요. 변경한 질문은 의도 라벨을 확인할 때까지 별도 보관합니다.
