"""Download the menu images referenced by CAIFE's local menu snapshot."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests

HOST = 'img.mega-mgccoffee.com'
AGENT = 'CAIFE-Education-Menu-Research/1.0'
MAX_BYTES = 12 * 1024 * 1024
MIME_EXT = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}


def valid_image(data, mime):
    if mime == 'image/png': return data.startswith(b'\x89PNG\r\n\x1a\n')
    if mime == 'image/jpeg': return data.startswith(b'\xff\xd8\xff')
    if mime == 'image/webp': return len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    return False


def run(menu_file, output, delay):
    items = json.loads(menu_file.read_text(encoding='utf-8'))
    if not isinstance(items, list) or not items: raise ValueError('메뉴 목록이 비어 있습니다.')
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / 'index.json'
    prior = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    if not isinstance(prior, dict): raise ValueError('이미지 색인 형식이 올바르지 않습니다.')
    session = requests.Session()
    session.headers.update({'User-Agent': AGENT})
    last = 0.0
    def get(url, **kwargs):
        nonlocal last
        wait = delay - (time.monotonic() - last)
        if wait > 0: time.sleep(wait)
        try: return session.get(url, timeout=30, allow_redirects=False, **kwargs)
        finally: last = time.monotonic()
    robots_resp = get(f'https://{HOST}/robots.txt')
    if robots_resp.status_code == 404:
        robots = None
        robots_status = '404: 파일 없음'
    elif robots_resp.status_code == 200:
        robots = RobotFileParser()
        robots.parse(robots_resp.text.splitlines())
        robots_status = '200: 규칙 적용'
    else:
        raise RuntimeError(f'이미지 서버 robots.txt 응답 {robots_resp.status_code}: 수집 중단')
    mapping = {}
    url_cache = {}
    errors = []
    for n, item in enumerate(items, 1):
        item_id, url = item.get('id'), item.get('image_url')
        if not isinstance(item_id, str) or not re.fullmatch(r'[0-9a-f]{20}', item_id):
            errors.append({'id': item_id, 'error': '유효하지 않은 메뉴 ID'}); continue
        if not isinstance(url, str):
            errors.append({'id': item_id, 'error': '이미지 주소 없음'}); continue
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.netloc != HOST or not parts.path.startswith('/megahp/manager/upload/menu/') or parts.query or parts.fragment:
            errors.append({'id': item_id, 'error': '허용되지 않은 이미지 주소'}); continue
        if robots and not robots.can_fetch(AGENT, url):
            errors.append({'id': item_id, 'error': 'robots.txt 접근 금지'}); continue
        existing = prior.get(item_id)
        if isinstance(existing, str) and re.fullmatch(re.escape(item_id) + r'\.(?:png|jpg|webp)', existing):
            p = output / existing
            if p.is_file() and 0 < p.stat().st_size <= MAX_BYTES:
                data = p.read_bytes()
                mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp'}[p.suffix]
                if valid_image(data, mime):
                    mapping[item_id] = existing
                    url_cache[url] = p
                    continue
        if url in url_cache:
            filename = item_id + url_cache[url].suffix
            shutil.copyfile(url_cache[url], output / filename)
            mapping[item_id] = filename
            continue
        try:
            response = get(url, stream=True)
            if response.status_code in (403, 429) or 300 <= response.status_code < 400:
                raise RuntimeError(f'HTTP {response.status_code}: 수집 중단')
            if response.status_code != 200:
                errors.append({'id': item_id, 'error': f'HTTP {response.status_code}'}); continue
            mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
            ext = MIME_EXT.get(mime)
            if not ext:
                errors.append({'id': item_id, 'error': f'지원하지 않는 유형: {mime}'}); continue
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES: raise ValueError('이미지 최대 크기 초과')
                chunks.append(chunk)
            data = b''.join(chunks)
            if not valid_image(data, mime): raise ValueError('이미지 내용이 유형과 일치하지 않음')
            filename = item_id + ext
            (output / filename).write_bytes(data)
            mapping[item_id] = filename
            url_cache[url] = output / filename
            if n % 20 == 0 or n == len(items): print(f'{n}/{len(items)} 처리, 성공 {len(mapping)}', flush=True)
        except (requests.RequestException, ValueError) as exc:
            errors.append({'id': item_id, 'error': str(exc)})
        except RuntimeError as exc:
            errors.append({'id': item_id, 'error': str(exc)})
            break
        finally:
            index_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
    index_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'total': len(items), 'downloaded': len(mapping), 'errors': errors, 'robots': robots_status, 'delay_seconds': delay}
    (output / 'download_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if len(mapping) == len(items) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--menu-file', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--delay', type=float, default=1.0)
    args = parser.parse_args()
    if args.delay < 1: parser.error('--delay는 1초 이상이어야 합니다.')
    raise SystemExit(run(args.menu_file, args.output_dir, args.delay))
