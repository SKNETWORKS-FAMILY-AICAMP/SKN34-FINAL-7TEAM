# CAIFE

작은 글씨와 복잡한 화면이 어려운 고객이 음성과 쉬운 화면으로 카페 메뉴를 고르도록 돕는 키오스크 프로젝트입니다.

현재 React + FastAPI 기반의 **주문 연습 화면**을 구현했습니다. 브라우저 음성 합성으로 안내를 듣고, 메뉴 검색·카테고리·크게 보기, 옵션 선택, 주문 목록과 결제 연습 흐름을 사용할 수 있습니다. 실제 주문·결제는 이뤄지지 않습니다. 음성 인식(STT)과 AI 대화 주문은 아직 구현하지 않았습니다.

## 주요 폴더

- `frontend/src`: 첫 화면, 메뉴와 주문 화면, 음성 안내, 스타일
- `backend/app`: 메뉴·이미지와 서버 상태 API
- `backend/tests`: 백엔드 API 테스트
- `scripts/mega`: 메가MGC커피 메뉴·이미지·지점 가격 수집기와 테스트
- `data/menus/mega`: 로컬 수집 데이터와 이미지 (Git 추적 제외)
- `docs/`: 프로젝트 문서

## 메뉴 데이터 준비

메뉴 화면은 `data/menus/mega/mega_menu.json`과 `data/menus/mega/images`의 로컬 데이터를 사용합니다. 수집 데이터와 사진은 GitHub에 포함되지 않으므로 별도로 준비해야 합니다. 데이터가 없으면 메뉴 API는 오류를 표시합니다.

아래 명령은 메뉴 데이터가 없는 새 환경에서 최초로 수집할 때 사용합니다. 이미 가격을 입력한 메뉴 파일이 있다면 덮어쓰므로 아래 명령을 그대로 실행하지 마세요. 가격 수집은 선택 사항이며, 고색산업단지점의 수집 당시 기본가 중 일치하는 메뉴에만 연결합니다.

```powershell
python -m pip install -r scripts/mega/requirements.txt
python scripts/mega/mega_collector.py --output-dir data/menus/mega
python scripts/mega/download_images.py --menu-file data/menus/mega/mega_menu.json --output-dir data/menus/mega/images
python scripts/mega/collect_passorder_prices.py --menu-file data/menus/mega/mega_menu.json --output-file data/menus/mega/mega_menu_priced.json
Move-Item -LiteralPath data/menus/mega/mega_menu_priced.json -Destination data/menus/mega/mega_menu.json -Force
```

사용자가 입력한 가격 엑셀은 다음과 같이 별도 파일로 적용할 수 있습니다. 엑셀은 개인 로컬에 보관하고, 결과를 확인한 후 메뉴 JSON을 교체하세요. 공식 메뉴 수집기는 결과 파일을 새로 만들므로 기존 메뉴 파일에 직접 재수집하면 수동 가격이 사라질 수 있습니다. 재수집 시 별도 폴더에 저장하고 가격 엑셀을 다시 적용하세요. 지점 가격 수집기는 수동 입력 가격을 보존합니다.

```powershell
python scripts/mega/import_prices.py --workbook <가격입력엑셀경로> --menu-file data/menus/mega/mega_menu.json --output-file data/menus/mega/mega_menu_updated.json
```

출처는 [메가MGC커피 공식 메뉴](https://www.mega-mgccoffee.com/menu/menu.php?category=1&menu_category1=1&menu_category2=1&page=1)와 [패스오더 고색산업단지점 메뉴](https://app.passorder.co.kr/normal/4d1abd73-c5bb-45d0-b787-ff341b9f84f9/menus)입니다. 가격과 이미지의 이용 범위는 해당 자료의 이용 조건을 따릅니다. 수집 방법과 저장 필드는 `scripts/mega/README.md` 및 `scripts/mega/README_images.md`를 참고하세요.

## Docker로 실행하기

Docker Desktop을 실행한 상태에서 프로젝트 루트에서 다음을 실행합니다.

```powershell
docker compose up --build
```

- 화면: http://localhost:5173
- API 상태: http://localhost:8000/api/health
- 메뉴 API: http://localhost:8000/api/menus
- API 문서: http://localhost:8000/docs

종료할 때 터미널에서 `Ctrl+C`를 누릅니다. 컨테이너를 재사용하지 않을 경우 `docker compose down`으로 정리할 수 있습니다.

필요하면 `.env.example`을 `.env`로 복사해 포트를 변경할 수 있습니다. AI·TTS API 키 항목은 아직 기능에 연결되지 않은 자리입니다. 실제 키는 `.env`에만 저장하고 GitHub에 올리지 않습니다.

```powershell
Copy-Item .env.example .env
```

## Docker 없이 개발하기

Python 3.12와 Node.js 24 기준입니다. 각각 별도 터미널에서 실행합니다.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm ci
npm run dev
```

기본 개발 화면은 `http://localhost:5173`, 백엔드는 `http://127.0.0.1:8000`입니다. 프론트엔드는 `/api` 요청을 백엔드로 전달합니다. `.env`는 Docker Compose 실행 시 백엔드에 전달되며, 로컬 Python 실행 시 자동으로 읽도록 아직 설정하지 않았습니다.

## 다음 개발 순서

1. 메뉴 정보와 주문 발화를 연결해 텍스트 대화를 구현합니다.
2. 음성 입력을 붙이고 손님이 내용을 확인·수정할 수 있도록 합니다.
3. 음성 주문에서 메뉴와 옵션이 빠지면 질문하고, 확인된 주문을 목록에 담습니다.
4. 결제 테스트 연동을 진행합니다.
