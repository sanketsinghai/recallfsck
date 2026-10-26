import argparse
import asyncio
import json
import sys
from html import escape
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from .backends import QdrantIndex, SQLiteIndex
from .engine import SCHEDULES, run_case


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run disposable knowledge lifecycle experiments")
    parser.add_argument("command", choices=["demo", "test", "replay"])
    parser.add_argument("artifact", nargs="?")
    parser.add_argument("--backend", choices=["sqlite", "qdrant"], default="sqlite")
    parser.add_argument("--url", default="http://localhost:6333")
    parser.add_argument("--worker", choices=["buggy", "fixed"], default="fixed")
    parser.add_argument("--output", type=Path, default=Path("report"))
    args = parser.parse_args(argv)
    if args.artifact and args.command != "replay":
        parser.error("an artifact is only accepted by replay")
    factory = SQLiteIndex if args.backend == "sqlite" else lambda: QdrantIndex(args.url)
    try:
        cases = []
        if args.command == "replay":
            if not args.artifact:
                parser.error("replay requires a case JSON path")
            saved = json.loads(Path(args.artifact).read_text())
            if not isinstance(saved, dict):
                raise ValueError("Replay artifact must be a JSON object")
            if saved["schema_version"] != 1 or saved["backend"] != args.backend:
                raise ValueError("Schema/backend mismatch; explicitly select the saved backend")
            specs = [(saved["worker"], saved["scenario"], saved["schedule"])]
        else:
            workers = ["buggy", "fixed"] if args.command == "demo" else [args.worker]
            specs = [(worker, name, None) for worker in workers for name in SCHEDULES]
        args.output.mkdir(parents=True, exist_ok=True)
        # Remove aggregate evidence from an earlier run before beginning this run.
        for filename in ("summary.json", "junit.xml", "index.html", "error.json"):
            (args.output / filename).unlink(missing_ok=True)
        for worker, name, schedule in specs:
            case = asyncio.run(run_case(factory, worker, name, schedule))
            case.update(
                schema_version=1,
                backend=args.backend,
                scope="Synthetic fixture; this schedule and these retrieval paths only. "
                "No physical erasure or general concurrency guarantee.",
            )
            path = args.output / f"{worker}-{name}.json"
            path.write_text(json.dumps(case, indent=2) + "\n")
            print(f"{case['status']:4} {worker:5} {name} ({path})")
            cases.append(case)
        suite = Element(
            "testsuite",
            name="recallfsck",
            tests=str(len(cases)),
            failures=str(sum(c["status"] == "FAIL" for c in cases)),
        )
        for case in cases:
            node = SubElement(suite, "testcase", name=case["worker"] + ":" + case["scenario"])
            if case["status"] == "FAIL":
                SubElement(
                    node, "failure", message="Observed state differs from reference"
                ).text = json.dumps(case)
        ElementTree(suite).write(args.output / "junit.xml", encoding="unicode", xml_declaration=True)
        (args.output / "summary.json").write_text(json.dumps(cases, indent=2) + "\n")
        rows = "".join(
            "<tr><td>"
            + "</td><td>".join(
                escape(str(case[key]))
                for key in ("worker", "scenario", "status", "expected_live_ids", "observations")
            )
            + "</td></tr>"
            for case in cases
        )
        (args.output / "index.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<title>RecallFSCK evidence</title><style>body{font:16px system-ui;margin:2rem}"
            "table{border-collapse:collapse}td,th{padding:1rem;border:1px solid #aaa;text-align:left}"
            "</style><h1>RecallFSCK evidence</h1><p>Backend: "
            + escape(args.backend)
            + "</p><p>Controlled synthetic fixtures only. No general concurrency or physical erasure guarantee.</p>"
            "<table><tr><th>Worker</th><th>Scenario</th><th>Result</th><th>Expected IDs</th>"
            "<th>Observed evidence</th></tr>" + rows + "</table></html>"
        )
        if args.command == "demo":
            expected = ["PASS", "PASS", "FAIL", "PASS", "PASS", "PASS"]
            ok = [case["status"] for case in cases] == expected
            print(
                "Demo verified: buggy race detected; fixed schedule passed."
                if ok
                else "Demo did not match expected results."
            )
            return 0 if ok else 1
        return int(any(case["status"] == "FAIL" for case in cases))
    except (OSError, ValueError, KeyError, TypeError, TimeoutError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        try:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "error.json").write_text(
                json.dumps({"status": "ERROR", "backend": args.backend, "message": str(error)}, indent=2)
                + "\n"
            )
        except OSError:
            pass
        return 2
