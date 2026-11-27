"""Tests for M6 promotion guardrails."""
import tempfile, unittest
from pathlib import Path
from digitalbrain.evolution import SQLitePromotionStore

class PromotionGuardrailTests(unittest.TestCase):
    def test_production_promoted_requires_human_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'p.db'
            with SQLitePromotionStore(db) as store:
                with self.assertRaises(ValueError):
                    store.record(artifact='a', from_env='validation', to_env='production', status='promoted', reason='auto', metadata={})
                store.record(artifact='a', from_env='validation', to_env='production', status='proposed', reason='candidate', metadata={'human_approval': True})
                store.record(artifact='a', from_env='validation', to_env='production', status='approved', reason='approved', metadata={'human_approval': True})
                rec = store.record(artifact='a', from_env='validation', to_env='production', status='promoted', reason='promoted', metadata={'human_approval': True})
                self.assertEqual(rec.status, 'promoted')

if __name__=='__main__':
    unittest.main()
