"""Tests for promotion workflow state transitions (M6 baseline)."""
import tempfile, unittest
from pathlib import Path
from digitalbrain.evolution import SQLitePromotionStore

class PromotionWorkflowTests(unittest.TestCase):
    def test_workflow_requires_approval_before_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'p.db'
            with SQLitePromotionStore(db) as store:
                with self.assertRaises(ValueError):
                    store.record(artifact='a', from_env='validation', to_env='production', status='promoted', reason='skip', metadata={'human_approval': True})
                gate = {'passed': True, 'evidence': {'comparison': 'candidate_better'}}
                store.record(artifact='a', from_env='validation', to_env='production', status='proposed', reason='candidate', metadata={'human_approval': True})
                store.record(artifact='a', from_env='validation', to_env='production', status='approved', reason='ok', metadata={'human_approval': True, 'evaluation_gate': gate})
                rec = store.record(artifact='a', from_env='validation', to_env='production', status='promoted', reason='ok', metadata={'human_approval': True, 'evaluation_gate': gate})
                self.assertEqual(rec.status, 'promoted')

if __name__ == '__main__':
    unittest.main()
