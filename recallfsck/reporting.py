"""Single evidence writer for successful, failed and errored cases."""

import json
import re
from html import escape
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement


def write_reports(cases, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for case in cases:
        name = f"{case['worker']}-{case['scenario']}"
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError("Invalid report case name")
        (output / (name + ".json")).write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    suite = Element(
        "testsuite",
        name="recallfsck",
        tests=str(len(cases)),
        failures=str(sum(case["status"] == "FAIL" for case in cases)),
        errors=str(sum(case["status"] == "ERROR" for case in cases)),
    )
    for case in cases:
        node = SubElement(suite, "testcase", name=case["worker"] + ":" + case["scenario"])
        if case["status"] != "PASS":
            tag = "failure" if case["status"] == "FAIL" else "error"
            SubElement(node, tag, message=case["status"]).text = json.dumps(case)
    ElementTree(suite).write(output / "junit.xml", encoding="utf-8", xml_declaration=True)
    rows = []
    for case in cases:
        name = f"{case['worker']}-{case['scenario']}.json"
        rows.append(
            "<tr><td>"
            + "</td><td>".join(escape(str(case[key])) for key in ("backend", "worker", "scenario", "status"))
            + '</td><td><a href="'
            + name
            + '">JSON</a><details><summary>Evidence</summary><pre>'
            + escape(
                json.dumps(case.get("first_divergence") or case.get("error") or case.get("checks"), indent=2)
            )
            + "</pre></details></td></tr>"
        )
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>RecallFSCK report</title><style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:1rem}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #aaa;padding:1rem;text-align:left}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}</style>"
        "<h1>RecallFSCK evidence</h1><p>Results cover only the executed adapter, retrieval paths, synthetic vectors, "
        "operation schedules and observation windows. Retrieval absence does not establish physical erasure.</p>"
        "<table><tr><th>Backend</th><th>Application</th><th>Scenario</th><th>Result</th><th>Evidence</th></tr>"
        + "".join(rows)
        + "</table></html>",
        encoding="utf-8",
    )
