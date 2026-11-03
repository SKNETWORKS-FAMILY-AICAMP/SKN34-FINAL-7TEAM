from __future__ import annotations
import argparse, csv, hashlib, json, re, sys, time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

BASE = 'https://www.mega-mgccoffee.com'
INDEX = BASE + '/menu/'
MENU = BASE + '/menu/menu.php'
AGENT = 'CAIFE-Education-Menu-Research/1.0'
GROUPS = {'1': '음료', '2': '푸드'}

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() or None if node else None

def parse_categories(html):
    result = []
    for control in BeautifulSoup(html, 'html.parser').select('input[name="list_checkbox"]'):
        label = control.find_parent('label')
        name = text(label.select_one('.checkbox_text')) if label else None
        value = control.get('value')
        if not value or not name:
            raise ValueError('분류 이름 또는 코드가 없습니다.')
        result.append((value, name))
    if not result or len({v for v,n in result}) != len(result):
        raise ValueError('분류가 없거나 코드가 중복됩니다.')
    return result

def item_key(item):
    fields = [item['name'], item['temperature'], item['image_url']]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()[:20]

def parse_page(html, group, source_url, collected_at):
    soup = BeautifulSoup(html, 'html.parser')
    listing, pages = soup.select_one('ul#menu_list'), soup.select_one('ul#board_page')
    if listing is None or pages is None:
        raise ValueError(f'메뉴 목록 또는 페이지 표기가 없습니다: {source_url}')
    last = pages.select_one('a.board_page_last[data-page]')
    numbered = [int(a['data-page']) for a in pages.select('a[data-page]') if a['data-page'].isdigit()]
    active = text(pages.select_one('.board_page_check a'))
    if active and active.isdigit(): numbered.append(int(active))
    last_page = int(last['data-page']) if last and last['data-page'].isdigit() else max([1]+numbered)
    result = []
    for li in listing.find_all('li', recursive=False):
        card, detail = li.select_one('.cont_gallery_list_box'), li.select_one('.inner_modal')
        if card is None or detail is None:
            raise ValueError(f'카드 또는 상세 정보 누락: {source_url}')
        name = text(card.select_one('.cont_text_title b'))
        box = detail.select_one('.cont_text_box')
        blocks = box.find_all('div', class_='cont_text', recursive=False) if box else []
        if not name or len(blocks) < 3:
            raise ValueError(f'메뉴명 또는 상세 정보 구조 오류: {source_url}')
        dimensions = blocks[1].find_all('div', class_='cont_text_inner', recursive=False)
        img = card.select_one('img[src]')
        nutrition = [text(n) for n in detail.select('.cont_list li') if text(n)]
        value = lambda key: next((n for n in nutrition if n.startswith(key)), None)
        allergy = next((text(b) for b in blocks[2:] if 'cont_text_info' in (b.get('class') or [])), None)
        caffeine = value('카페인')
        item = {'name':name, 'name_en':text(card.select_one('.cont_text_info .text1')),
                'group':group, 'categories':[], 'temperature':text(card.select_one('.cont_gallery_list_label')),
                'serving_size_raw':text(dimensions[0]) if dimensions else None,
                'calories_raw':text(dimensions[1]) if len(dimensions)>1 else None,
                'description_raw':text(card.select_one('.cont_text_info .text2')), 'allergen_raw':allergy,
                'saturated_fat_raw':value('포화지방'), 'sugar_raw':value('당류'), 'sodium_raw':value('나트륨'),
                'protein_raw':value('단백질'), 'caffeine_raw':caffeine, 'nutrients_raw':nutrition,
                'price':None, 'shots':None, 'order_options':None, 'is_new':False,
                'image_url':urljoin(BASE, img['src']) if img else None, 'source_url':source_url,
                'collected_at':collected_at,
                'quality_flags':['caffeine_unit_g_review'] if caffeine and re.match(r'카페인\s*[\d,.]+\s*g(?:\s|$)',caffeine,re.I) else []}
        item['id'] = item_key(item)
        result.append(item)
    return result,last_page

class Collector:
    def __init__(self, delay):
        self.session=requests.Session()
        self.session.headers.update({'User-Agent':AGENT})
        self.delay=delay
        self.last_request=0.0
        self.robots=None
    def get(self,url,params=None):
        wait=self.delay-(time.monotonic()-self.last_request)
        if wait>0: time.sleep(wait)
        final_url=requests.Request('GET', url, params=params).prepare().url
        if self.robots and not self.robots.can_fetch(AGENT, final_url): raise RuntimeError(f'robots.txt 금지: {final_url}')
        response=self.session.get(url,params=params,timeout=30,allow_redirects=False)
        self.last_request=time.monotonic()
        if response.status_code!=200: raise RuntimeError(f'HTTP {response.status_code}: {response.url}')
        return response
    def check_robots(self):
        response=self.get(BASE+'/robots.txt')
        self.robots=RobotFileParser(); self.robots.parse(response.text.splitlines())
        for url in (INDEX,MENU):
            if not self.robots.can_fetch(AGENT,url): raise RuntimeError(f'robots.txt 금지: {url}')
    def categories(self,group):
        return parse_categories(self.get(INDEX,{'menu_category1':group,'menu_category2':group}).text)
    def pages(self,group,category=None):
        params={'menu_category1':group,'menu_category2':group}
        if category is None: params['list_checkbox_all']='all'
        else: params['category']=category
        page,last,items,seen=1,None,[],set()
        while True:
            params['page']=page
            response=self.get(MENU,params)
            parsed,current_last=parse_page(response.text,GROUPS[group],response.url,datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))
            if last is None:
                last=current_last
                if last>200: raise RuntimeError(f'비정상 페이지 수: {last}')
            elif last!=current_last: raise RuntimeError(f'페이지 수가 수집 중 변경: {response.url}')
            if not parsed: raise RuntimeError(f'빈 페이지: {response.url}')
            for item in parsed:
                if item['id'] in seen: raise RuntimeError(f'페이지 내 중복 또는 식별 충돌: {item["name"]}')
                seen.add(item['id'])
            items.extend(parsed)
            print(f'{GROUPS[group]} / {category or "전체"}: {page}/{last} ({len(parsed)}개)',file=sys.stderr,flush=True)
            if page>=last: return items,last
            page+=1
    def run(self):
        self.check_robots(); all_items=[]; summary={}
        for group_id, group in GROUPS.items():
            categories=self.categories(group_id)
            items,pages=self.pages(group_id)
            by_id={item['id']:item for item in items}
            category_counts={}
            for category_id,name in categories:
                members,n_pages=self.pages(group_id,category_id)
                unmatched=[i['name'] for i in members if i['id'] not in by_id]
                if unmatched: raise RuntimeError(f'{group} {name}: 전체에 없는 항목 {unmatched[:5]}')
                for member in members:
                    record=by_id[member['id']]; record['categories'].append(name)
                    if name=='신상품': record['is_new']=True
                category_counts[name]={'items':len(members),'pages':n_pages}
            summary[group]={'items':len(items),'pages':pages,'categories':category_counts,
                            'uncategorized':[i['name'] for i in items if not i['categories']]}
            all_items.extend(items)
        return all_items,summary

def save(out,items,summary):
    out.mkdir(parents=True,exist_ok=True)
    manifest={'generated_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'), 'item_count':len(items),
              'groups':summary,'quality_flag_counts':dict(Counter(f for i in items for f in i['quality_flags'])),
              'coverage':'수집 시점의 공식 음료·푸드 분류. 과거 단종 메뉴 및 지점별 판매 여부는 포함을 보장하지 않음.', 'source':INDEX}
    (out/'mega_menu.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'mega_menu.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0])); writer.writeheader()
        for item in items: writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in item.items()})
    (out/'mega_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'items':len(items),'output_dir':str(out)},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description='메가MGC커피 공식 음료·푸드 메뉴 수집기')
    p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--delay',type=float,default=2.0)
    a=p.parse_args()
    if a.delay<1: p.error('--delay는 1초 이상이어야 합니다.')
    try:
        items,summary=Collector(a.delay).run(); save(a.output_dir,items,summary)
    except (requests.RequestException,RuntimeError,ValueError) as exc:
        print(f'수집 실패: {exc}',file=sys.stderr); return 1
    return 0
if __name__=='__main__': raise SystemExit(main())


