"""Tests for baseline vs candidate outcome comparison."""
import tempfile, unittest
from pathlib import Path
from digitalbrain.learning import SQLiteOutcomeStore

class OutcomeComparisonTests(unittest.TestCase):
    def test_compare_baseline_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'o.db'
            with SQLiteOutcomeStore(db) as store:
                store.record_outcome(kind='bench', ref_id='base', status='passed')
                store.record_outcome(kind='bench', ref_id='base', status='failed')
                store.record_outcome(kind='bench', ref_id='cand', status='passed')
                store.record_outcome(kind='bench', ref_id='cand', status='passed')
                rep = store.compare_baseline_candidate(kind='bench', baseline_ref='base', candidate_ref='cand')
                self.assertEqual(rep['recommendation'], 'candidate_better')
                self.assertGreater(rep['delta'], 0)

if __name__ == '__main__':
    unittest.main()
