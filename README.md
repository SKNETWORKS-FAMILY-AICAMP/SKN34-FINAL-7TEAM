# CAIFE

음성과 쉬운 화면으로 카페 주문을 돕는 AI 키오스크 프로젝트입니다.

목표: 손님의 말이나 화면 선택으로 음료를 고르고, AI가 주문을 확인하며 TTS로 안내합니다. 결제는 이후 테스트 환경 연동을 검토합니다.

## 폴더 구성

- `frontend/src/features/voice`: 음성 입력과 재생 UI
- `frontend/src/features/conversation`: 대화 화면과 대화 상태
- `frontend/src/features/order`: 메뉴 선택, 장바구니, 주문 확인
- `frontend/src/components`, `frontend/src/styles`: 공통 UI와 스타일
- `backend/app/api`: 클라이언트 요청을 받는 API
- `backend/app/services/ai`: 대화 처리와 메뉴 기반 답변
- `backend/app/services/stt`, `backend/app/services/tts`: 음성 인식과 음성 생성
- `backend/app/services/orders`: 주문 정보와 금액 처리
- `backend/app/services/payments`: 추후 결제 연동
- `backend/app/models`: 메뉴와 주문 데이터 구조
- `data/menus`: 가상 카페의 시연용 메뉴 데이터
- `assets/images`, `assets/audio`: 직접 제작하거나 이용 권한이 있는 시연용 자료
- `docs`: 요구사항, 흐름과 설계 문서
- `tests`: 기능과 시연 흐름 검증

## 개발 순서

1. 가상 메뉴 데이터를 만들고 텍스트 대화를 구현합니다.
2. AI 응답을 TTS로 들려주고 화면에 크게 표시합니다.
3. 음성 입력을 붙이고 손님이 말한 내용을 확인·수정할 수 있도록 합니다.
4. 메뉴와 옵션을 확인해 주문을 완성하고, 결제 테스트 연동을 검토합니다.

현재는 폴더 구조만 준비된 상태입니다. 프레임워크, AI·음성 서비스와 결제 서비스는 아직 정하지 않았으며 실행 가능한 앱은 포함되어 있지 않습니다. API 키와 비밀번호는 저장소에 올리지 않습니다.
