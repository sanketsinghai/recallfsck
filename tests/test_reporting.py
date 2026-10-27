import json
from html.parser import HTMLParser
from xml.etree.ElementTree import parse

import pytest

from recallfsck.reporting import write_reports


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def case(status="PASS", name="create", **kwargs):
    return {
        "backend": "sqlite",
        "application": "example.integration:real_app",
        "worker": "fixed",
        "scenario": name,
        "status": status,
        "duration_seconds": 0.25,
        **kwargs,
    }


def test_application_and_worker_are_distinct_aligned_columns(tmp_path):
    write_reports([case()], tmp_path)
    table = Tables()
    table.feed((tmp_path / "index.html").read_text())
    header, row = table.rows[:2]
    assert len(header) == len(row)
    assert row[header.index("Application")] == "example.integration:real_app"
    assert row[header.index("Worker")] == "fixed"
    assert row[header.index("Backend")] == "sqlite"


def test_html_json_junit_agree_on_counts_identity_and_time(tmp_path):
    cases = [
        case(),
        case("FAIL", "deleted", first_divergence={"expected": [], "observed": [{"id": 42}]}),
        case("ERROR", "offline", error={"type": "OSError", "message": "Service unavailable"}),
    ]
    write_reports(cases, tmp_path)
    manifest = json.loads((tmp_path / "report.json").read_text())
    assert manifest["counts"] == {"total": 3, "pass": 1, "fail": 1, "error": 1}
    assert manifest["status"] == "ERROR"
    assert manifest["duration_seconds"] == 0.75
    assert manifest["run_id"] and manifest["generated_at"].endswith("+00:00")
    assert json.loads((tmp_path / "summary.json").read_text()) == cases
    suite = parse(tmp_path / "junit.xml").getroot()
    assert {k: suite.attrib[k] for k in ("tests", "failures", "errors", "skipped", "time")} == {
        "tests": "3",
        "failures": "1",
        "errors": "1",
        "skipped": "0",
        "time": "0.750000",
    }
    assert len(suite.findall("testcase/failure")) == 1
    assert len(suite.findall("testcase/error")) == 1
    for node in suite.findall("testcase"):
        props = {prop.attrib["name"]: prop.attrib["value"] for prop in node.findall("properties/property")}
        assert props["application"] == "example.integration:real_app"
        assert props["worker"] == "fixed" and node.attrib["time"] == "0.250000"


def test_legacy_case_does_not_invent_identity_or_measured_duration(tmp_path):
    legacy = case()
    legacy.pop("application")
    legacy.pop("duration_seconds")
    write_reports([legacy], tmp_path)
    manifest = json.loads((tmp_path / "report.json").read_text())
    assert manifest["cases"][0]["application"] == "fixture"
    assert manifest["duration_seconds"] is None
    assert "time" not in parse(tmp_path / "junit.xml").getroot().attrib


def test_empty_report_is_not_a_safety_pass(tmp_path):
    write_reports([], tmp_path)
    assert json.loads((tmp_path / "report.json").read_text())["status"] == "NOT RUN"
    assert "No test cases were executed" in (tmp_path / "index.html").read_text()


@pytest.mark.parametrize("bad", [case("UNKNOWN"), case(name="../unsafe"), case(application=None)])
def test_invalid_reports_do_not_create_partial_output(tmp_path, bad):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        write_reports([case(), bad], output)
    assert not output.exists()


def test_duplicate_identity_is_rejected_before_overwriting_files(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        write_reports([case(), case()], tmp_path)
    assert not list(tmp_path.iterdir())


def test_demo_failure_stays_failure_and_xml_handles_source_control_characters(tmp_path):
    write_reports(
        [case("FAIL", first_divergence={"observed": "<script>\x01&"})],
        tmp_path,
        context={
            "command": "demo",
            "demo_outcomes_matched": True,
            "url": "postgresql://secret:password@server/db",
        },
    )
    html = (tmp_path / "index.html").read_text()
    assert "expected failure is not an integrity pass" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "secret:password" not in (tmp_path / "report.json").read_text()
    assert parse(tmp_path / "junit.xml").getroot().attrib["failures"] == "1"


def test_run_ids_change_between_executions(tmp_path):
    write_reports([case()], tmp_path)
    first = json.loads((tmp_path / "report.json").read_text())["run_id"]
    write_reports([case()], tmp_path)
    assert json.loads((tmp_path / "report.json").read_text())["run_id"] != first
