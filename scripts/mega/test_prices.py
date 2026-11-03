import unittest
from collect_passorder_prices import match_prices


def offering(name, price, description=''):
    return {'name': name, 'description': description, 'offers': {'price': str(price)}}


class MatchTests(unittest.TestCase):
    def test_only_verified_temperature_and_food_are_matched(self):
        items = [
            {'name': '아메리카노', 'temperature': 'HOT', 'group': '음료'},
            {'name': '아메리카노', 'temperature': 'ICE', 'group': '음료'},
            {'name': '라떼', 'temperature': 'ICE', 'group': '음료'},
            {'name': '쿠키', 'temperature': None, 'group': '푸드'},
            {'name': '한정', 'temperature': 'ICE', 'group': '음료'},
        ]
        sections = [
            {'name': '커피', 'hasMenuItem': [offering('핫 아메리카노', 1700), offering('아이스 아메리카노', 2000), offering('라떼', 2900), offering('쿠키', 1500)]},
            {'name': '선착순 한정 이벤트', 'hasMenuItem': [offering('한정 (Only ICE)', 100)]},
        ]
        result, count = match_prices(items, sections, '2026-11-03T10:00:00+09:00')
        self.assertEqual([item['price'] for item in result], [1700, 2000, None, 1500, None])
        self.assertEqual(count, 3)
        self.assertEqual(result[0]['price_source']['store'], '메가MGC커피 고색산업단지점')
        self.assertNotIn('price_source', result[2])

    def test_conflicting_price_is_not_matched(self):
        items = [{'name': '아메리카노', 'temperature': 'ICE', 'group': '음료'}]
        sections = [{'name': '커피', 'hasMenuItem': [offering('아이스 아메리카노', 2000), offering('아이스 아메리카노', 2100)]}]
        result, count = match_prices(items, sections, 'now')
        self.assertIsNone(result[0]['price'])
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()
