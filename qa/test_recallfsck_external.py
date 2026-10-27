"""Reconstructed seven-case review coverage against the installed package.

The review's original archive was not attached. These are new self-contained
controls, not the original scripts or independent adopter evidence. No comparator
or product application fixture is copied or imported.
"""

import argparse
import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path

from recallfsck.reporting import write_reports
from recallfsck.stores import SQLiteStore, ordered
from recallfsck.suite import run_sequence


class IndependentApplication:
    def __init__(self, store, fault=None):
        self.store, self.fault = store, fault
        self.source = {}
        self.epochs = {}

    async def put(self, document):
        previous = self.source.get(document.key)
        self.source[document.key] = document
        self.epochs[document.key] = self.epochs.get(document.key, 0) + 1
        if self.fault == "stale" and previous:
            self.store.upsert(previous)
        else:
            self.store.upsert(document)
        if self.fault == "duplicate" and previous:
            self.store.upsert(replace(document, id=99))

    async def delete(self, tenant, doc_id):
        key = f"{tenant}:{doc_id}"
        self.source.pop(key, None)
        self.epochs[key] = self.epochs.get(key, 0) + 1
        self.store.delete(tenant, doc_id)

    async def migrate(self):
        for key, document in list(self.source.items()):
            updated = replace(document, model="v2")
            self.source[key] = updated
            self.epochs[key] += 1
            if self.fault == "loss":
                self.store.delete(document.tenant, document.id)
            else:
                self.store.upsert(updated)

    async def index(self, tenant, doc_id, paused, resume):
        key = f"{tenant}:{doc_id}"
        captured, epoch = self.source[key], self.epochs[key]
        paused.set()
        await resume.wait()
        if self.fault == "resurrection" or (key in self.source and self.epochs[key] == epoch):
            self.store.upsert(captured)

    def retrieve(self, tenant, model):
        if self.fault == "leak":
            return ordered([row for row in self.store.scan() if row["model"] == model])
        return self.store.query(tenant, model)


CASES = [
    ("valid-create", None, ["insert", "observe"], "PASS"),
    ("valid-delete-race", None, ["insert", "start_index", "delete", "resume_index", "observe"], "PASS"),
    ("resurrection", "resurrection", ["insert", "start_index", "delete", "resume_index", "observe"], "FAIL"),
    ("stale-revision", "stale", ["insert", "replace", "observe"], "FAIL"),
    ("tenant-leakage", "leak", ["insert", "insert_beta", "observe"], "FAIL"),
    ("migration-loss", "loss", ["insert", "insert_beta", "migrate", "observe"], "FAIL"),
    ("duplicate-record", "duplicate", ["insert", "insert", "observe"], "FAIL"),
]


def run_cases(output):
    cases = []
    for name, fault, schedule, expected in CASES:
        started = time.perf_counter()
        result = asyncio.run(
            run_sequence(
                SQLiteStore,
                "fixed",
                name,
                schedule,
                consistency_seconds=0,
                monitor_seconds=0,
                poll_seconds=0.001,
                app_factory=lambda store, worker, fault=fault: IndependentApplication(store, fault),
            )
        )
        result.update(
            backend="sqlite",
            application="qa.IndependentApplication",
            duration_seconds=time.perf_counter() - started,
            cli_replay_supported=False,
            qa_expectation={
                "expected_integrity_status": expected,
                "matched": result["status"] == expected,
                "fault": fault,
            },
            provenance="New reconstruction of review categories; original QA scripts were not supplied.",
        )
        cases.append(result)
        print(f"{result['status']:4} {name} (expected {expected})")
    write_reports(cases, output)
    summary = {
        "cases": len(cases),
        "expected_pass_verdicts": 2,
        "expected_fail_verdicts": 5,
        "expectations_met": sum(case["qa_expectation"]["matched"] for case in cases),
        "scope": "Self-contained adapter controls against the actual installed package; not independent adopter validation.",
    }
    Path(output, "qa-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert summary["expectations_met"] == 7, summary
    assert sum(case["status"] == "PASS" for case in cases) == 2
    assert sum(case["status"] == "FAIL" for case in cases) == 5
    print("QA expectations met: 7/7; actual integrity verdicts: 2 PASS, 5 FAIL.")
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("report/seven-case-qa"))
    args = parser.parse_args()
    run_cases(args.output)


if __name__ == "__main__":
    main()
