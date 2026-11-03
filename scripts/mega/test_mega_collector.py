import unittest
from mega_collector import parse_categories,parse_page

class TestParsing(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(parse_categories('<label><input name="list_checkbox" value="9"><div class="checkbox_text">신상품</div></label>'), [('9','신상품')])
    def test_missing_categories_fails(self):
        with self.assertRaises(ValueError): parse_categories('<html></html>')
    def test_current_final_page_and_raw_caffeine_unit(self):
        html='''<ul id="menu_list"><li><div class="cont_gallery_list_box"><div class="cont_gallery_list_label">HOT</div><img src="https://img.example/a.png"><div class="cont_text_title"><b>커피</b></div><div class="cont_text_info"><span class="text1">Coffee</span><span class="text2">안내</span></div></div><div class="inner_modal"><div class="cont_text_box"><div class="cont_text">제목</div><div class="cont_text"><div class="cont_text_inner">컵용량 : 591ml</div><div class="cont_text_inner">1회 제공량 20kcal</div></div><div class="cont_text">설명</div><div class="cont_text cont_text_info">알레르기 성분 :</div></div><div class="cont_list"><ul><li>카페인 236.0g</li></ul></div></div></li></ul><ul id="board_page"><li><a data-page="1">처음</a></li><li class="board_page_check"><a>9</a></li><li><a class="board_page_last">마지막</a></li></ul>'''
        rows,last=parse_page(html,'음료','https://example.org','2026-11-02')
        self.assertEqual(last,9)
        self.assertEqual(rows[0]['caffeine_raw'],'카페인 236.0g')
        self.assertEqual(rows[0]['quality_flags'],['caffeine_unit_g_review'])
        self.assertEqual(rows[0]['temperature'],'HOT')
        self.assertIsNone(rows[0]['price'])
    def test_bad_markup_fails(self):
        with self.assertRaises(ValueError): parse_page('<html></html>','음료','https://example.org','2026')

if __name__ == '__main__': unittest.main()
