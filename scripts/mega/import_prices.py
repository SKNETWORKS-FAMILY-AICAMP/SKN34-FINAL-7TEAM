"""Import user-entered menu prices from the CAIFE price workbook.

Input and output are explicit. The original menu JSON is not overwritten.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

HEADERS = ('메뉴명', '온도', '종류', '가격 입력 (원)', '메뉴 ID')
TEMPERATURES = {'ICE': '차갑게', 'HOT': '따뜻하게', None: '표기 없음'}


def apply_rows(menu, rows, entered_at):
    """Match records by ID, validate prices and preserve other sources."""
    indexed = {item['id']: item for item in menu}
    if len(indexed) != len(menu):
        raise ValueError('메뉴 데이터의 ID가 중복됩니다.')
    output = [dict(item) for item in menu]
    result_by_id = {item['id']: item for item in output}
    seen = set()
    warnings = []
    changed = 0
    blank = 0
    for row_number, row in enumerate(rows, start=5):
        name, temp, group, price, menu_id = row
        if all(value is None for value in row):
            continue
        if not isinstance(menu_id, str) or menu_id not in indexed:
            raise ValueError(f'{row_number}행의 메뉴 ID를 찾을 수 없습니다.')
        if menu_id in seen:
            raise ValueError(f'{row_number}행의 메뉴 ID가 중복됩니다.')
        seen.add(menu_id)
        item = result_by_id[menu_id]
        if temp != TEMPERATURES.get(item.get('temperature')) or group != item.get('group'):
            raise ValueError(f'{row_number}행의 온도 또는 종류가 메뉴 데이터와 다릅니다.')
        if name != item.get('name'):
            warnings.append({'row': row_number, 'id': menu_id, 'menu_name': item.get('name'), 'workbook_name': name})
        if price is None or (isinstance(price, str) and not price.strip()):
            blank += 1
            continue
        if isinstance(price, str):
            clean = price.strip().replace(',', '')
            if not re.fullmatch(r'\d+', clean):
                raise ValueError(f'{row_number}행의 가격은 원 단위 숫자로 입력해 주세요.')
            price = int(clean)
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not float(price).is_integer() or not 0 <= price <= 1000000:
            raise ValueError(f'{row_number}행의 가격은 0~1,000,000 사이 정수여야 합니다.')
        price = int(price)
        source = item.get('price_source') or {}
        if item.get('price') is not None and source.get('kind') != 'user_entered':
            if item['price'] == price:
                continue
            raise ValueError(f'{row_number}행은 이미 다른 출처의 가격이 있어 덮어쓰지 않았습니다.')
        item['price'] = price
        item['price_source'] = {'kind': 'user_entered', 'entered_at': entered_at}
        changed += 1
    return output, {'updated': changed, 'blank': blank, 'name_mismatches': warnings}


def main():
    parser = argparse.ArgumentParser(description='엑셀에 직접 입력한 가격을 메뉴 ID로 연결합니다.')
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--menu-file', type=Path, required=True)
    parser.add_argument('--output-file', type=Path, required=True)
    args = parser.parse_args()
    if args.menu_file.resolve() == args.output_file.resolve():
        raise ValueError('안전한 검토를 위해 출력 파일은 원본 메뉴 파일과 다르게 지정해 주세요.')
    workbook = load_workbook(args.workbook, read_only=True, data_only=False)
    try:
        sheet = workbook.worksheets[0]
        if tuple(next(sheet.iter_rows(min_row=4, max_row=4, max_col=5, values_only=True))) != HEADERS:
            raise ValueError('엑셀의 항목 이름을 확인해 주세요.')
        rows = []
        for cells in sheet.iter_rows(min_row=5, max_col=5):
            if cells[3].data_type == 'f':
                raise ValueError(f'{cells[3].row}행 가격은 수식이 아닌 숫자로 입력해 주세요.')
            rows.append(tuple(cell.value for cell in cells))
    finally:
        workbook.close()
    menu = json.loads(args.menu_file.read_text(encoding='utf-8'))
    result, report = apply_rows(menu, rows, datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
