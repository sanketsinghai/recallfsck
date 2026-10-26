import asyncio
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from recallfsck.backends import QdrantIndex, SQLiteIndex
from recallfsck.cli import main
from recallfsck.engine import SCHEDULES, run_case


class LifecycleTests(unittest.TestCase):
    def test_red_green_schedule_repeated(self):
        for _ in range(20):
            for worker in ("buggy", "fixed"):
                for scenario in SCHEDULES:
                    with self.subTest(worker=worker, scenario=scenario):
                        result = asyncio.run(run_case(SQLiteIndex, worker, scenario))
                        fails = worker == "buggy" and scenario == "delete-during-index"
                        self.assertEqual(result["status"], "FAIL" if fails else "PASS")
                        self.assertEqual(len(result["observations"]), 2)
                        if fails:
                            self.assertEqual(result["expected_live_ids"], [])
                            self.assertEqual(result["first_divergence"]["ids"], [42])

    def test_replay_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["demo", "--output", tmp]), 0)
            artifact = str(Path(tmp) / "buggy-delete-during-index.json")
            original = json.loads(Path(artifact).read_text())
            self.assertEqual(main(["replay", artifact, "--output", tmp]), 1)
            self.assertEqual(json.loads(Path(artifact).read_text()), original)
            self.assertEqual(main(["test", "--worker", "fixed", "--output", tmp]), 0)
            self.assertEqual(main(["test", "--worker", "buggy", "--output", tmp]), 1)

    def test_unknown_schedule_rejected(self):
        with self.assertRaises(ValueError):
            asyncio.run(run_case(SQLiteIndex, "fixed", "create", ["observe"]))

    def test_invalid_replay_inputs(self):
        invalid = [
            [],
            {},
            {"schema_version": 99, "backend": "sqlite"},
            {
                "schema_version": 1,
                "backend": "sqlite",
                "worker": "../bad",
                "scenario": "create",
                "schedule": SCHEDULES["create"],
            },
            {
                "schema_version": 1,
                "backend": "sqlite",
                "worker": "fixed",
                "scenario": "missing",
                "schedule": [],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = Path(tmp) / "input.json"
            for value in invalid:
                path.write_text(json.dumps(value))
                self.assertEqual(main(["replay", str(path), "--output", tmp]), 2)
                self.assertEqual(json.loads((Path(tmp) / "error.json").read_text())["status"], "ERROR")

    def test_backend_error_cleans_up(self):
        class BrokenIndex(SQLiteIndex):
            closed = False

            def search(self):
                raise OSError("injected retrieval failure")

            def close(self):
                self.closed = True
                super().close()

        index = BrokenIndex()
        with self.assertRaisesRegex(OSError, "injected"):
            asyncio.run(run_case(lambda: index, "fixed", "create"))
        self.assertTrue(index.closed)

    @unittest.skipUnless(os.environ.get("RECALLFSCK_QDRANT_URL"), "requires disposable Qdrant")
    def test_real_qdrant_red_green_and_cleanup(self):
        indexes = []

        def factory():
            index = QdrantIndex(os.environ["RECALLFSCK_QDRANT_URL"])
            indexes.append(index)
            return index

        for worker in ("buggy", "fixed"):
            for scenario in SCHEDULES:
                result = asyncio.run(run_case(factory, worker, scenario))
                self.assertEqual(
                    result["status"],
                    "FAIL" if worker == "buggy" and scenario == "delete-during-index" else "PASS",
                )
        from urllib.error import HTTPError

        for index in indexes:
            with self.assertRaises(HTTPError) as raised:
                index.request("GET", "")
            self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
