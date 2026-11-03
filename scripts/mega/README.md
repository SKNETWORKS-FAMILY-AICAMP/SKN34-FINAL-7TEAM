# 메가MGC커피 메뉴 수집기

공식 메뉴 페이지의 음료·푸드 전체 및 각 세부 분류를 수집합니다. 수집 시점의 신상품 분류는 `is_new`로 표시합니다. 음료의 HOT/ICE는 별도 레코드로 보존합니다. 굿즈는 제외합니다.

## 실행

Python 3.10 이상에서:

```powershell
python -m pip install -r requirements.txt
python mega_collector.py --output-dir "C:\CAIFE-data\mega" --delay 2
```

결과 디렉터리는 저장소 밖의 별도 폴더를 지정하세요. `--delay`는 요청 간격(초)이며 기본 2초, 최소 1초입니다. 수집 전에 공식 `robots.txt`를 확인합니다. 사이트의 응답 실패, 제한·리디렉션, 예상치 못한 HTML, 분류와 전체 목록 불일치가 있으면 수집을 중단합니다.

- `mega_menu.json`: 중첩 목록을 포함한 UTF-8 JSON
- `mega_menu.csv`: Excel에서 열기 쉬운 UTF-8 BOM CSV. 배열 항목은 JSON 문자열
- `mega_manifest.json`: 수집 일시, 분류별 건수·페이지 수, 미분류 메뉴와 데이터 이상 점검 수

카드명, 영문명, 표시된 HOT/ICE, 용량·제공량·열량 원문, 설명·알레르기·영양값 원문, 이미지 URL, 분류, 출처 URL 및 수집 시각을 저장합니다. 이미지를 다운로드하지 않습니다. 가격·샷 수·주문 옵션은 홈페이지에서 확인되지 않으면 `null`입니다. 실제 표시값이 비어 있는 것과 0은 다르며, 단위나 숫자를 자동 추정하지 않습니다. 카페인 g 등 이상 단위는 원문을 유지하고 `quality_flags`에 표시합니다.

전체·신상품은 사이트의 수집 시점 분류를 의미합니다. 과거 시즌·단종 메뉴나 매장별 판매 상태까지 보장하지 않습니다. 홈페이지 메뉴 데이터·사진 이용과 외부 공개 범위는 해당 권리자의 조건을 따릅니다.

## 검증

```powershell
python -m unittest -v test_mega_collector
```
