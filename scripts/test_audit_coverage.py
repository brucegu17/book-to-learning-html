#!/usr/bin/env python3
"""Python 3.11+: run isolated coverage-ledger regression cases."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_coverage.py")


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = b"test source"
        (self.root / "source.txt").write_bytes(source)
        (self.root / "notes.md").write_text("Test point", encoding="utf-8")
        self.data = {
            "source": {"path": "source.txt", "sha256": hashlib.sha256(source).hexdigest(), "pages": 2},
            "scope": {"included": [{"start": 1, "end": 2}], "excluded": []},
            "units": [{"id": "u1", "title": "Unit", "start": 1, "end": 2,
                       "review_status": "complete", "review_notes": "Checked both pages"}],
            "items": [{"id": "i1", "unit_id": "u1", "kind": "claim", "source_pages": [1],
                       "point": "Test point", "attribution": "book", "disposition": "covered",
                       "targets": ["notes.md"], "review_status": "complete"}],
        }

    def run_audit(self, exit_code=0, complete=False):
        ledger = self.root / "coverage.json"
        ledger.write_text(json.dumps(self.data), encoding="utf-8")
        # Run outside the ledger directory to verify relative-path resolution.
        run = subprocess.run([sys.executable, str(SCRIPT), str(ledger)],
                             cwd=SCRIPT.parent, capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual(run.returncode, exit_code, result)
        self.assertEqual(result["structure_valid"], exit_code == 0)
        self.assertEqual(result["recorded_review_complete"], complete, result)
        self.assertEqual(result["semantic_completeness"], "not_proven_by_this_script")
        return result

    def test_complete_record(self):
        self.run_audit(complete=True)

    def test_pending_exits_zero_but_incomplete(self):
        self.data["items"][0]["disposition"] = "pending"
        self.run_audit()

    def test_unaccounted_page(self):
        self.data["source"]["pages"] = 3
        self.run_audit(exit_code=1)

    def test_missing_output(self):
        self.data["items"][0]["targets"] = ["missing.md"]
        self.run_audit(exit_code=1)

    def test_source_hash_mismatch(self):
        self.data["source"]["sha256"] = "0" * 64
        self.run_audit(exit_code=1)

    def test_out_of_range_citation(self):
        self.data["items"][0]["source_pages"] = [3]
        self.run_audit(exit_code=1)

    def test_empty_reviewed_unit(self):
        self.data["items"] = []
        result = self.run_audit(exit_code=1)
        self.assertTrue(result["recorded_book_candidates_empty"])
        self.assertEqual(result["units_without_book_candidates"], ["u1"])

    def test_duplicate_item(self):
        self.data["items"].append(dict(self.data["items"][0]))
        self.run_audit(exit_code=1)

    def test_contradictory_scope(self):
        self.data["scope"]["excluded"] = [{"start": 2, "end": 2, "reason": "Test"}]
        self.run_audit(exit_code=1)

    def test_editor_only_never_complete(self):
        self.data["items"][0]["attribution"] = "editor"
        result = self.run_audit()
        self.assertEqual(result["recorded_book_items"], {})
        self.assertTrue(result["recorded_book_candidates_empty"])
        self.assertEqual(result["units_without_book_candidates"], ["u1"])

    def test_all_empty_with_reason_still_incomplete(self):
        self.data["items"] = []
        self.data["units"][0]["no_book_candidates_reason"] = "Only blank practice space"
        result = self.run_audit()
        self.assertTrue(result["recorded_book_candidates_empty"])
        self.assertEqual(result["book_candidate_exceptions"], {"u1": "Only blank practice space"})

    def add_empty_unit(self):
        self.data["units"][0]["end"] = 1
        self.data["units"].append({"id": "u2", "title": "Practice space", "start": 2, "end": 2,
                                   "review_status": "complete", "review_notes": "Checked page"})

    def test_one_empty_unit_with_reason(self):
        self.add_empty_unit()
        self.data["units"][1]["no_book_candidates_reason"] = "Blank practice space"
        result = self.run_audit(complete=True)
        self.assertFalse(result["recorded_book_candidates_empty"])
        self.assertEqual(result["units_without_book_candidates"], ["u2"])

    def test_one_editor_only_unit_without_reason(self):
        self.add_empty_unit()
        self.data["items"].append(dict(self.data["items"][0], id="i2", unit_id="u2",
                                       source_pages=[2], attribution="editor"))
        self.run_audit()

    def test_blank_or_invalid_exception_reason(self):
        self.data["items"] = []
        for reason in ("  ", None, 123):
            with self.subTest(reason=reason):
                self.data["units"][0]["no_book_candidates_reason"] = reason
                self.run_audit(exit_code=1)

    def test_exception_conflicts_with_book_item(self):
        self.data["units"][0]["no_book_candidates_reason"] = "Invalid exception"
        self.run_audit(exit_code=1)

    def test_exception_still_requires_unit_review(self):
        self.add_empty_unit()
        self.data["units"][1].update(no_book_candidates_reason="Blank space", review_status="partial")
        self.run_audit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
