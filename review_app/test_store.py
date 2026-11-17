import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('review_store', Path(__file__).with_name('store.py'))
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class ReviewStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        store.DB_PATH = Path(self.temp.name) / 'reviews.sqlite3'

    def tearDown(self):
        self.temp.cleanup()

    def test_review_saved_and_updated_with_history(self):
        store.save_review('id', '수정 필요', '질문', '행동', '', '이유')
        self.assertEqual(store.get_reviews()['id']['status'], '수정 필요')
        store.save_review('id', '승인', '수정 질문', '수정 행동', '안내', '')
        row = store.get_reviews()['id']
        self.assertEqual((row['status'], row['question']), ('승인', '수정 질문'))
        with store.closing(store.connect()) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM review_history').fetchone()[0], 2)

    def test_approval_requires_expected_action(self):
        with self.assertRaises(ValueError):
            store.save_review('id', '승인', '질문', '', '', '')
        self.assertEqual(store.get_reviews(), {})

    def test_export_excludes_holdout_and_rejected(self):
        rows = [{'key': str(i), 'split': split, 'question': '질문', 'group_id': 'g', 'source': '합성', 'dataset': '단일'}
                for i, split in enumerate(('train', 'test', 'train', 'holdout'))]
        for index, status in enumerate(('승인', '승인', '반려', '승인')):
            store.save_review(str(index), status, '질문', '행동', '', '')
        exported = [json.loads(line) for line in store.approved_jsonl(rows, store.get_reviews()).splitlines()]
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]['question_id'], '0')
        self.assertEqual(exported[0]['original_split'], 'train')

    def test_existing_dataset_ids_are_unique(self):
        if not any(path.exists() for path, _ in store.DATA_FILES):
            self.skipTest('local source files not available')
        rows, missing, errors = store.load_questions()
        self.assertFalse(errors, errors)
        self.assertEqual(len(rows), len({row['key'] for row in rows}))
        self.assertTrue(all(row['question'] and row['split'] for row in rows))


if __name__ == '__main__':
    unittest.main()

