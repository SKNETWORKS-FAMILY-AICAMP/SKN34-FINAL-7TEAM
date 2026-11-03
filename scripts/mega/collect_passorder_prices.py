"""Collect and conservatively match one store's publicly listed base prices."""
import argparse
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = 'https://app.passorder.co.kr'
STORE_URL = BASE + '/normal/4d1abd73-c5bb-45d0-b787-ff341b9f84f9/menus'
STORE = '메가MGC커피 고색산업단지점'
AGENT = 'CAIFE-Education-Menu-Research/1.0'


def normalized(value):
    return re.sub(r'\s+', '', value).casefold()


def parse_item(item):
    """Name and temperature only when the store explicitly specifies them."""
    name = item['name'].strip()
    temperature = None
    suffix = re.search(r'\s*\(\s*(?:only\s*)?(ice|hot)\s*\)\s*$', name, re.I)
    prefix = re.match(r'^(아이스|핫)\s+', name)
    if suffix:
        temperature = suffix.group(1).upper()
        name = name[:suffix.start()].strip()
    elif prefix:
        temperature = 'ICE' if prefix.group(1) == '아이스' else 'HOT'
        name = name[prefix.end():].strip()
    else:
        description = item.get('description', '')
        if re.search(r'\bonly\s*ice\b', description, re.I):
            temperature = 'ICE'
        elif re.search(r'\bonly\s*hot\b', description, re.I):
            temperature = 'HOT'
    return normalized(name), temperature


def match_prices(menu, sections, observed_at):
    index = defaultdict(set)
    for section in sections:
        if '이벤트' in section.get('name', ''):
            continue
        for item in section.get('hasMenuItem', []):
            price = item.get('offers', {}).get('price')
            if not isinstance(price, (str, int)) or not str(price).isdigit() or int(price) <= 0:
                continue
            key = parse_item(item)
            index[key].add(int(price))
    output = []
    matched = 0
    for original in menu:
        item = dict(original)
        # A store refresh must not erase prices supplied by the user.
        if (item.get('price_source') or {}).get('kind') == 'user_entered' and item.get('price') is not None:
            output.append(item)
            continue
        item['price'] = None
        item.pop('price_source', None)
        key = (normalized(item['name']), item.get('temperature'))
        # Do not infer an unspecified store drink temperature; food has no temperature.
        if item.get('temperature') is None and item.get('group') != '푸드':
            prices = set()
        else:
            prices = index.get(key, set())
        if len(prices) == 1:
            item['price'] = next(iter(prices))
            item['price_source'] = {'store': STORE, 'url': STORE_URL, 'collected_at': observed_at, 'kind': '기본가'}
            matched += 1
        output.append(item)
    return output, matched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--menu-file', type=Path, required=True)
    parser.add_argument('--output-file', type=Path, required=True)
    args = parser.parse_args()
    session = requests.Session()
    session.headers['User-Agent'] = AGENT
    robots = session.get(BASE + '/robots.txt', timeout=20, allow_redirects=False)
    robots.raise_for_status()
    policy = RobotFileParser(); policy.parse(robots.text.splitlines())
    if not policy.can_fetch(AGENT, STORE_URL):
        raise RuntimeError('robots.txt에서 메뉴 수집을 허용하지 않습니다.')
    time.sleep(1)
    response = session.get(STORE_URL, timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise RuntimeError(f'비정상 응답: {response.status_code}')
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    schemas = [json.loads(tag.string) for tag in soup.select('script[type="application/ld+json"]') if tag.string]
    root = next((s for s in schemas if s.get('@type') == 'FoodEstablishment'), None)
    if not root or 'hasMenuSection' not in root.get('hasMenu', {}):
        raise RuntimeError('메뉴 구조를 찾지 못했습니다.')
    menu = json.loads(args.menu_file.read_text(encoding='utf-8'))
    observed_at = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    result, matched = match_prices(menu, root['hasMenu']['hasMenuSection'], observed_at)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'matched': matched, 'total': len(result), 'collected_at': observed_at, 'source': STORE_URL}, ensure_ascii=False))


if __name__ == '__main__':
    main()
