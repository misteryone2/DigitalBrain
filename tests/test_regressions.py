"""Tests for M5 regression detection."""
import tempfile, unittest
from pathlib import Path
from digitalbrain.learning import SQLiteOutcomeStore

class RegressionTests(unittest.TestCase):
    def test_detect_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'o.db'
            with SQLiteOutcomeStore(db) as store:
                for _ in range(5):
                    store.record_outcome(kind='tool', ref_id='p', status='passed')
                for _ in range(5):
                    store.record_outcome(kind='tool', ref_id='r', status='failed')
                rep = store.detect_regressions(kind='tool', window=5, min_samples=5, drop_threshold=0.2)
                self.assertTrue(rep['enough_samples'])
                self.assertTrue(rep['regressed'])
                self.assertGreaterEqual(rep['drop'], 0.2)
if __name__=='__main__':
    unittest.main()
