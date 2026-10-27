import argparse
import asyncio
import json
import sys
from pathlib import Path

from .backends import QdrantIndex, SQLiteIndex
from .engine import SCHEDULES, run_case
from .reporting import write_reports


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
        for filename in ("summary.json", "report.json", "junit.xml", "index.html", "error.json"):
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
        matched = [case["status"] for case in cases] == ["PASS", "PASS", "FAIL", "PASS", "PASS", "PASS"]
        write_reports(cases, args.output, context={"command": args.command, "demo_outcomes_matched": matched})
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
        print(
            f"ERROR: {type(error).__name__}; check artifact input and disposable service availability.",
            file=sys.stderr,
        )
        try:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "error.json").write_text(
                json.dumps(
                    {"status": "ERROR", "backend": args.backend, "type": type(error).__name__}, indent=2
                )
                + "\n"
            )
            write_reports(
                cases
                + [
                    {
                        "backend": args.backend,
                        "application": "fixture",
                        "worker": "configuration",
                        "scenario": "legacy-execution",
                        "status": "ERROR",
                        "error": {
                            "type": type(error).__name__,
                            "message": "Legacy execution did not complete; check input and disposable service availability.",
                        },
                    }
                ],
                args.output,
                context={"command": args.command},
            )
        except OSError:
            pass
        return 2
