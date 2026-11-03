import unittest
from import_prices import apply_rows


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.items = [{'id': '1', 'name': '아메리카노', 'temperature': 'ICE', 'group': '음료', 'price': None}]
        self.row = ('아메리카노', '차갑게', '음료', 2000, '1')

    def test_import_preserves_item_and_marks_source(self):
        result, report = apply_rows(self.items, [self.row], 'now')
        self.assertEqual(result[0]['price'], 2000)
        self.assertEqual(result[0]['price_source'], {'kind': 'user_entered', 'entered_at': 'now'})
        self.assertEqual(report['updated'], 1)
        self.assertIsNone(self.items[0]['price'])

    def test_name_difference_is_reported_but_id_controls_matching(self):
        result, report = apply_rows(self.items, [('아아', '차갑게', '음료', 2000, '1')], 'now')
        self.assertEqual(result[0]['name'], '아메리카노')
        self.assertEqual(report['name_mismatches'][0]['id'], '1')

    def test_unknown_duplicate_or_mismatched_temperature_are_rejected(self):
        for rows in [[('아메리카노', '차갑게', '음료', 2000, 'bad')], [self.row, self.row], [('아메리카노', '따뜻하게', '음료', 2000, '1')]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                apply_rows(self.items, rows, 'now')

    def test_existing_store_price_is_not_overwritten(self):
        items = [{**self.items[0], 'price': 1700, 'price_source': {'kind': '기본가'}}]
        with self.assertRaises(ValueError):
            apply_rows(items, [self.row], 'now')

    def test_invalid_price_is_rejected(self):
        for invalid in [-1, 1.5, True, '=1+1', 'unknown']:
            row = ('아메리카노', '차갑게', '음료', invalid, '1')
            with self.subTest(price=invalid), self.assertRaises(ValueError):
                apply_rows(self.items, [row], 'now')


if __name__ == '__main__':
    unittest.main()
