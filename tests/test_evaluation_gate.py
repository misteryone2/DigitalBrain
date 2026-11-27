"""Tests for deterministic promotion evaluation gate (M5/M6 bridge)."""
import tempfile, unittest
from pathlib import Path
from digitalbrain.learning import SQLiteOutcomeStore, evaluate_promotion_gate

class EvaluationGateTests(unittest.TestCase):
    def test_gate_passes_when_candidate_not_worse(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'o.db'
            with SQLiteOutcomeStore(db) as store:
                store.record_outcome(kind='bench', ref_id='base', status='passed')
                store.record_outcome(kind='bench', ref_id='base', status='failed')
                store.record_outcome(kind='bench', ref_id='cand', status='passed')
                store.record_outcome(kind='bench', ref_id='cand', status='passed')
                gate = evaluate_promotion_gate(store, kind='bench', baseline_ref='base', candidate_ref='cand')
                self.assertTrue(gate['passed'])
                self.assertEqual(gate['comparison']['recommendation'], 'candidate_better')

    def test_gate_fails_on_regression_or_worse_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'o.db'
            with SQLiteOutcomeStore(db) as store:
                store.record_outcome(kind='bench', ref_id='base', status='passed')
                store.record_outcome(kind='bench', ref_id='base', status='passed')
                store.record_outcome(kind='bench', ref_id='cand', status='failed')
                gate = evaluate_promotion_gate(store, kind='bench', baseline_ref='base', candidate_ref='cand')
                self.assertFalse(gate['passed'])

if __name__ == '__main__':
    unittest.main()
