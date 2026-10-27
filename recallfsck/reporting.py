"""Portable HTML, JSON run manifest and JUnit XML from observed case evidence."""

import json
import math
import re
import shlex
import uuid
from datetime import datetime, timezone
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

STATUSES = ("PASS", "FAIL", "ERROR")
REPORT_SCOPE = (
    "Results cover only the executed application, backend, retrieval paths, operation schedules "
    "and finite observation windows. Retrieval absence does not establish physical erasure. "
    "Supplied fixtures and synthetic embeddings do not establish production correctness or independent adoption."
)


def _duration(case):
    value = case.get("duration_seconds")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        return None
    return float(value)


def _json(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def _xml_text(value):
    # XML 1.0 excludes several control characters which can appear in source text.
    return "".join(
        char
        if char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
        else "\ufffd"
        for char in str(value)
    )


def _replay(case, filename):
    if not case.get("cli_replay_supported", True):
        return None
    if case.get("schema_version") not in (1, 2) or not case.get("schedule"):
        return None
    args = ["recallfsck", "replay", filename, "--backend", case["backend"], "--output", "replayed"]
    application = case.get("application", "fixture")
    if application != "fixture":
        args += ["--app", application]
    return shlex.join(args)


def _details(case):
    blocks = []
    if case.get("first_divergence"):
        blocks.append(("First divergence: expected and observed", case["first_divergence"]))
    if case.get("error"):
        blocks.append(("Execution error", case["error"]))
    if case.get("schedule"):
        blocks.append(("Operation schedule", case["schedule"]))
    if case.get("history"):
        blocks.append(("Reference state history", case["history"]))
    if case.get("settings"):
        blocks.append(("Consistency and monitoring settings", case["settings"]))
    if case.get("checks"):
        blocks.append(("Observed checks and timing", case["checks"]))
    if "expected_live_ids" in case:
        blocks.append(("Expected legacy live IDs", case["expected_live_ids"]))
    if case.get("observations"):
        blocks.append(("Observed legacy retrieval paths", case["observations"]))
    if case.get("qa_expectation"):
        blocks.append(("QA expectation (separate from integrity verdict)", case["qa_expectation"]))
    return (
        "".join(
            "<details><summary>"
            + escape(label)
            + "</summary><pre>"
            + escape(_json(value))
            + "</pre></details>"
            for label, value in blocks
        )
        or '<p class="muted">No additional execution evidence was recorded.</p>'
    )


def write_reports(cases, output, *, context=None):
    """Keep summary.json's list format; add report.json with versioned run metadata.

    Validate the entire run before writing. Missing legacy application identifiers
    are labeled 'fixture', independently of their worker. Unknown durations remain
    unknown rather than being represented as measured zero-duration executions.
    """
    prepared, names = [], set()
    for original in cases:
        case = dict(original)
        for key in ("backend", "worker", "scenario"):
            if not isinstance(case.get(key), str) or not case[key]:
                raise ValueError(f"Missing or invalid report field: {key}")
        case.setdefault("application", "fixture")
        if not isinstance(case["application"], str) or not case["application"]:
            raise ValueError("Invalid application identifier")
        if case.get("status") not in STATUSES:
            raise ValueError("Invalid case status")
        name = f"{case['worker']}-{case['scenario']}.json"
        if not re.fullmatch(r"[a-z0-9_-]+\.json", name):
            raise ValueError("Invalid report case name")
        if name in names:
            raise ValueError("Duplicate case identity; use unique scenario names")
        names.add(name)
        _json(case)
        prepared.append(case)
    cases = prepared
    context = dict(context or {})
    # Only these non-secret command facts are persisted, never URLs, DSNs or argv.
    context = {key: context[key] for key in ("command", "demo_outcomes_matched") if key in context}
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        package_version = version("recallfsck")
    except PackageNotFoundError:
        package_version = "not installed"
    counts = {status.lower(): sum(case["status"] == status for case in cases) for status in STATUSES}
    durations = [_duration(case) for case in cases]
    total_duration = sum(durations) if cases and all(value is not None for value in durations) else None
    overall = "ERROR" if counts["error"] else "FAIL" if counts["fail"] else "PASS" if cases else "NOT RUN"
    manifest = {
        "report_schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "generated_at": generated,
        "package_version": package_version,
        "status": overall,
        "counts": {"total": len(cases), **counts},
        "duration_seconds": total_duration,
        "timing_coverage": {
            "measured_cases": sum(value is not None for value in durations),
            "total_cases": len(cases),
        },
        "context": context,
        "scope": REPORT_SCOPE,
        "cases": cases,
    }
    # Serialize before touching the destination so invalid metadata cannot produce a partial new run.
    manifest_json = _json(manifest)
    summary_json = _json(cases)
    suite = Element(
        "testsuite",
        name="recallfsck",
        tests=str(len(cases)),
        failures=str(counts["fail"]),
        errors=str(counts["error"]),
        skipped="0",
    )
    if total_duration is not None:
        suite.set("time", f"{total_duration:.6f}")
    properties = SubElement(suite, "properties")
    for key in ("run_id", "generated_at", "package_version", "scope"):
        SubElement(properties, "property", name=key, value=_xml_text(manifest[key]))
    for case, duration in zip(cases, durations):
        node = SubElement(
            suite,
            "testcase",
            name=_xml_text(case["worker"] + ":" + case["scenario"]),
            classname=_xml_text("recallfsck." + case["backend"] + "." + case["application"]),
        )
        if duration is not None:
            node.set("time", f"{duration:.6f}")
        props = SubElement(node, "properties")
        for key in ("backend", "application", "worker", "scenario", "status"):
            SubElement(props, "property", name=key, value=_xml_text(case[key]))
        if case["status"] != "PASS":
            tag = "failure" if case["status"] == "FAIL" else "error"
            error_type = (
                case.get("error", {}).get("type", "ExecutionError")
                if tag == "error"
                else "IntegrityViolation"
            )
            SubElement(
                node, tag, type=_xml_text(error_type), message=_xml_text(case["status"])
            ).text = _xml_text(_json(case))
    rows = []
    for number, case in enumerate(cases, 1):
        filename = f"{case['worker']}-{case['scenario']}.json"
        duration = _duration(case)
        cells = "".join(
            "<td>" + escape(case[key]) + "</td>" for key in ("backend", "application", "worker", "scenario")
        )
        status = case["status"]
        command = _replay(case, filename)
        replay = (
            (
                "<p><strong>Replay from this report folder</strong></p><pre>"
                + escape(command)
                + '</pre><p class="muted">Use the original disposable endpoint separately for remote backends; '
                "credentials are not recorded. Replay exits 1 when it reproduces an integrity failure.</p>"
            )
            if command
            else ""
        )
        rows.append(
            '<tr><th scope="row">'
            + str(number)
            + "</th>"
            + cells
            + '<td><span class="badge '
            + status.lower()
            + '">'
            + status
            + "</span></td><td>"
            + (f"{duration:.3f} s" if duration is not None else "Not recorded")
            + '</td><td><a href="'
            + filename
            + '">Case JSON</a><details><summary>View evidence and reproduction</summary>'
            + _details(case)
            + replay
            + "</details></td></tr>"
        )
    demo_note = ""
    if context.get("command") == "demo":
        outcome = "matched" if context.get("demo_outcomes_matched") else "did not match"
        demo_note = (
            '<aside class="note"><strong>Demonstration run.</strong> The buggy/corrected pattern '
            + outcome
            + " its expected outcomes. Deliberately injected defects remain FAIL in this report and JUnit; "
            "an expected failure is not an integrity pass.</aside>"
        )
    duration_text = f"{total_duration:.3f} s" if total_duration is not None else "Not fully recorded"
    cards = "".join(
        '<div class="metric"><span>' + label + "</span><strong>" + str(value) + "</strong></div>"
        for label, value in (
            ("Total cases", len(cases)),
            ("Passed", counts["pass"]),
            ("Failed", counts["fail"]),
            ("Errors", counts["error"]),
        )
    )
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RecallFSCK — Knowledge Integrity Report</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;color:#172439;background:#f3f6fa}
*{box-sizing:border-box}body{margin:0}main{max-width:1440px;margin:auto;padding:40px 24px}
header{padding-bottom:24px;border-bottom:1px solid #ccd6e2}h1{font-size:30px;letter-spacing:-.7px;margin:8px 0}
h2{font-size:20px;margin-top:32px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:1.8px;color:#466181}
p{line-height:1.6}a{color:#164b94;text-underline-offset:3px}a:focus-visible,summary:focus-visible{outline:3px solid #306bba}
.muted,dt{color:#50627a}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}
.metric{background:white;border:1px solid #ccd6e2;border-radius:10px;padding:20px}.metric span{display:block;color:#50627a}
.metric strong{display:block;font-size:32px;margin-top:8px}.badge{display:inline-block;font-size:12px;font-weight:750;padding:5px 9px;border-radius:5px;white-space:nowrap}
.pass{color:#145333;background:#dff4e8}.fail{color:#912d28;background:#fbe5e3}.error{color:#74460c;background:#fff0d4}
.not-run{color:#44546b;background:#e2e8f0}.note{background:#e8f0fb;border-left:4px solid #356eb1;padding:16px;margin:24px 0;line-height:1.6}
dl{display:grid;grid-template-columns:140px 1fr;gap:8px 16px}dd{margin:0;overflow-wrap:anywhere}
.table-wrap{overflow-x:auto;border:1px solid #ccd6e2;border-radius:10px;background:white}
table{border-collapse:collapse;width:100%;font-size:14px}caption{text-align:left;padding:16px;font-weight:600}
th,td{border-top:1px solid #dce3ed;padding:14px 12px;text-align:left;vertical-align:top}thead{background:#edf2f8}
thead th{border-top:0}tbody th{font-weight:500;color:#50627a}td:last-child{min-width:280px;width:36%}
summary{cursor:pointer;color:#164b94;padding:8px 0}pre{font-size:12px;line-height:1.6;background:#f4f6f9;padding:12px;max-height:380px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;border-radius:5px}
footer{margin-top:32px;padding:20px 0;border-top:1px solid #ccd6e2;color:#50627a;font-size:13px}
@media(max-width:700px){main{padding:24px 12px}.metrics{grid-template-columns:repeat(2,1fr);gap:10px}h1{font-size:25px}dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:8px}}
@media print{body{background:white}main{padding:0}.table-wrap{overflow:visible}table{font-size:10px}pre{max-height:none}details{break-inside:avoid}a{color:inherit}}
</style></head><body><main><header><div class="eyebrow">RECALLFSCK / TEST EVIDENCE</div>
<h1>RecallFSCK evidence</h1><p>Knowledge integrity test report · observed application and index behavior</p>"""
    html += '<span class="badge ' + overall.lower().replace(" ", "-") + '">' + overall + "</span></header>"
    html += '<section aria-label="Run summary" class="metrics">' + cards + "</section>" + demo_note
    html += '<section aria-labelledby="run-details"><h2 id="run-details">Run details</h2><dl>'
    for label, value in (
        ("Run ID", manifest["run_id"]),
        ("Generated (UTC)", generated),
        ("Package", package_version),
        ("Case duration total", duration_text),
    ):
        html += "<dt>" + label + "</dt><dd>" + escape(str(value)) + "</dd>"
    html += '</dl><p><a href="report.json">Run manifest (JSON)</a> · <a href="summary.json">Cases (JSON)</a> · <a href="junit.xml">JUnit XML</a></p></section>'
    html += '<h2>Case results</h2><div class="table-wrap"><table><caption>Actual integrity verdicts; application identity and worker are separate fields.</caption>'
    html += '<thead><tr><th scope="col">#</th><th scope="col">Backend</th><th scope="col">Application</th><th scope="col">Worker</th><th scope="col">Scenario</th><th scope="col">Result</th><th scope="col">Duration</th><th scope="col">Evidence and reproduction</th></tr></thead><tbody>'
    html += "".join(rows) if rows else '<tr><td colspan="8">No test cases were executed.</td></tr>'
    html += (
        "</tbody></table></div><footer><strong>Scope and limits.</strong> "
        + escape(REPORT_SCOPE)
        + "</footer></main></body></html>"
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for case in cases:
        (output / f"{case['worker']}-{case['scenario']}.json").write_text(
            _json(case) + "\n", encoding="utf-8"
        )
    (output / "summary.json").write_text(summary_json + "\n", encoding="utf-8")
    (output / "report.json").write_text(manifest_json + "\n", encoding="utf-8")
    ElementTree(suite).write(output / "junit.xml", encoding="utf-8", xml_declaration=True)
    (output / "index.html").write_text(html, encoding="utf-8")
