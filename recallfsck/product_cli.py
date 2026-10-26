"""Release CLI; the original demo remains available as `legacy-demo`."""

import argparse
import asyncio
import importlib
import json
import os
import re
import sys
from pathlib import Path

from .reporting import write_reports
from .stores import store_factory
from .suite import SCENARIOS, WORKERS, FixtureApplication, minimize, run_sequence

DEFAULTS = {
    "backend": "sqlite",
    "worker": "fixed",
    "consistency_seconds": 0.1,
    "monitor_seconds": 0.02,
    "poll_seconds": 0.01,
    "output": "report",
}


def load_config(path):
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - set(DEFAULTS) - {"url", "scenarios"}:
        raise ValueError("Config must be a mapping containing documented keys only")
    return data


def resolve_app(spec):
    if spec is None:
        return FixtureApplication
    module, separator, name = spec.partition(":")
    if not separator or not name.isidentifier():
        raise ValueError("--app must be an installed module:factory")
    factory = getattr(importlib.import_module(module), name)
    if not callable(factory):
        raise ValueError("Application factory is not callable")
    return factory


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stateful knowledge integrity tests on disposable data")
    parser.add_argument(
        "command", choices=["init", "demo", "test", "replay", "minimize", "explore", "legacy-demo"]
    )
    parser.add_argument("artifact", nargs="?")
    parser.add_argument("--config")
    parser.add_argument("--backend", "--adapter", choices=["sqlite", "qdrant", "chroma", "pgvector"])
    parser.add_argument("--url", help="Disposable endpoint/DSN; prefer RECALLFSCK_URL for credentials")
    parser.add_argument("--worker", choices=WORKERS)
    parser.add_argument("--output")
    parser.add_argument("--scenario", action="append", choices=list(SCENARIOS))
    parser.add_argument("--consistency-seconds", type=float)
    parser.add_argument("--monitor-seconds", type=float)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--app", help="Explicitly execute a trusted installed module:factory")
    parser.add_argument("--examples", type=int, default=50)
    args = parser.parse_args(argv)
    if args.command == "legacy-demo":
        from .cli import main as legacy

        return legacy(["demo", "--output", args.output or "report/legacy"])
    options = dict(DEFAULTS)
    try:
        if args.command == "init":
            import yaml

            path = Path(args.config or "recallfsck.yaml")
            options["backend"] = args.backend or "sqlite"
            options["scenarios"] = list(SCENARIOS)
            # Exclusive create never silently replaces somebody's configuration.
            with path.open("x", encoding="utf-8") as handle:
                yaml.safe_dump(options, handle, sort_keys=False)
            print(f"Created {path}; run recallfsck test --config {path}")
            return 0
        if args.config:
            options.update(load_config(args.config))
        for key in (*DEFAULTS, "url"):
            value = getattr(args, key, None)
            if value is not None:
                options[key] = value
        url = args.url or os.environ.get("RECALLFSCK_URL") or options.get("url")
        factory = store_factory(options["backend"], url)
        app_factory = resolve_app(args.app)
        timing = {key: options[key] for key in ("consistency_seconds", "monitor_seconds", "poll_seconds")}
        if options["worker"] not in WORKERS:
            raise ValueError("Unknown worker")
        names = args.scenario or options.get("scenarios", list(SCENARIOS))
        if (
            not isinstance(names, list)
            or not names
            or any(not isinstance(name, str) or name not in SCENARIOS for name in names)
        ):
            raise ValueError("scenarios must be a nonempty list of supported scenario names")
        specs = []
        if args.command in ("replay", "minimize"):
            if not args.artifact:
                raise ValueError("A saved JSON artifact is required")
            artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
            if not isinstance(artifact, dict):
                raise ValueError("Artifact must be an object")
            if artifact.get("schema_version") == 1 and args.command == "replay":
                from .cli import main as legacy

                return legacy(
                    [
                        "replay",
                        args.artifact,
                        "--backend",
                        options["backend"],
                        "--output",
                        options["output"],
                        "--url",
                        url or "http://localhost:6333",
                    ]
                )
            if artifact.get("schema_version") != 2 or artifact.get("backend") != options["backend"]:
                raise ValueError("Schema/backend mismatch: explicitly choose the saved backend")
            if artifact.get("application", "fixture") != (args.app or "fixture"):
                raise ValueError("Replay requires the same explicit --app")
            name = artifact["scenario"]
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]{1,80}", name):
                raise ValueError("Invalid scenario name")
            timing.update(artifact["settings"])
            specs = [(artifact["worker"], name, artifact["schedule"])]
        elif args.artifact:
            raise ValueError("Only replay/minimize accept an artifact")
        elif args.command == "explore":
            from .discovery import discover

            schedule = discover(factory, options["worker"], args.examples, app_factory=app_factory, **timing)
            if schedule is None:
                print("No failure found within the configured search budget; no safety proof implied.")
                return 0
            specs = [(options["worker"], "generated", schedule)]
        else:
            workers = ["buggy", "fixed"] if args.command == "demo" else [options["worker"]]
            specs = [(worker, name, SCENARIOS[name]) for worker in workers for name in names]
        cases = []
        for worker, name, schedule in specs:
            try:
                if args.command == "minimize":
                    result = asyncio.run(minimize(factory, artifact, app_factory=app_factory, **timing))
                else:
                    result = asyncio.run(
                        run_sequence(factory, worker, name, schedule, app_factory=app_factory, **timing)
                    )
                result.update(backend=options["backend"], application=args.app or "fixture")
            except Exception as error:
                # Avoid credentials in driver exceptions/connection strings in persisted reports.
                result = {
                    "schema_version": 2,
                    "backend": options["backend"],
                    "application": args.app or "fixture",
                    "worker": worker,
                    "scenario": name,
                    "schedule": schedule,
                    "status": "ERROR",
                    "error": {
                        "type": type(error).__name__,
                        "message": "Execution failed; inspect adapter configuration and service availability.",
                    },
                }
                print(f"ERROR {worker} {name}: {type(error).__name__}", file=sys.stderr)
            cases.append(result)
            print(f"{result['status']:5} {worker:14} {name}")
        write_reports(cases, options["output"])
        if any(case["status"] == "ERROR" for case in cases):
            return 2
        if args.command == "demo":
            expected_failures = {"delete-during-index", "update-during-index", "migration-during-index"}
            matches = all(
                case["status"]
                == ("FAIL" if case["worker"] == "buggy" and case["scenario"] in expected_failures else "PASS")
                for case in cases
            )
            print("Demo matched expected red/green outcomes." if matches else "Unexpected demo outcomes.")
            return 0 if matches else 1
        return int(any(case["status"] == "FAIL" for case in cases))
    except Exception as error:
        print(
            f"ERROR: {type(error).__name__}: invalid input, missing optional dependency, or service unavailable. See docs/usage.md.",
            file=sys.stderr,
        )
        return 2
