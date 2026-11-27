"""Tests for M6 promotion/rollback baseline."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.evolution import SQLitePromotionStore


class PromotionTests(unittest.TestCase):
    def test_promotion_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "p.db"
            with SQLitePromotionStore(db) as store:
                store.record(artifact="plan:1", from_env="lab", to_env="validation", status="proposed", reason="candidate")
                rec = store.record(artifact="plan:1", from_env="lab", to_env="validation", status="approved", reason="tests passed")
                self.assertEqual(rec.to_env, "validation")
                recs = store.list()
                self.assertEqual(len(recs), 1)

    def test_invalid_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "p.db"
            with SQLitePromotionStore(db) as store:
                with self.assertRaises(ValueError):
                    store.record(artifact="x", from_env="dev", to_env="prod", status="x", reason="x")


if __name__ == "__main__":
    unittest.main()
