# 메가MGC커피 메뉴 이미지 수집

수집된 메뉴 JSON의 공식 이미지 URL을 이용해 이미지를 내려받습니다. PNG, JPEG, WebP만 허용하고 이미지 형식과 최대 크기를 확인합니다. 이미지 서버의 robots.txt를 먼저 확인하고 요청 사이에 최소 1초를 둡니다. 차단 응답이나 리디렉션이 있으면 중단합니다.

프로젝트 루트에서 다음 명령을 실행합니다. 먼저 메뉴 수집기로 `data/menus/mega/mega_menu.json`을 준비해야 합니다.

```powershell
python -m pip install -r scripts/mega/requirements.txt
python scripts/mega/download_images.py --menu-file data/menus/mega/mega_menu.json --output-dir data/menus/mega/images
```

`index.json`은 메뉴 ID와 저장한 파일명을 연결하며 `download_report.json`은 성공·실패를 기록합니다. 재실행할 때 정상 저장된 파일은 다시 내려받지 않습니다. 출력 폴더는 Git에서 제외되는 로컬 디렉터리를 사용합니다. 이미지의 재사용이나 공개 범위는 권리자의 조건을 따릅니다.
