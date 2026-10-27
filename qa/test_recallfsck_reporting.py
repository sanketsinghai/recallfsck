"""Application/Worker regression against an installed RecallFSCK distribution."""

import tempfile
from html.parser import HTMLParser
from pathlib import Path

from recallfsck.reporting import write_reports


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.current, self.cell, self.depth = [], None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current = []
        elif tag in ("th", "td") and self.current is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.current is not None and self.cell is not None:
            self.current.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None


def check_report():
    with tempfile.TemporaryDirectory() as tmp:
        identifier = "example.adapter:actual_application"
        write_reports(
            [
                {
                    "backend": "sqlite",
                    "application": identifier,
                    "worker": "fixed",
                    "scenario": "create",
                    "status": "PASS",
                }
            ],
            tmp,
        )
        parser = TableParser()
        parser.feed(Path(tmp, "index.html").read_text())
        header, row = parser.rows[:2]
        assert "Application" in header and "Worker" in header, header
        assert row[header.index("Application")] == identifier, row
        assert row[header.index("Worker")] == "fixed", row
        assert len(header) == len(row), (header, row)
    print("Reporting regression passed: actual application and worker have distinct aligned columns.")


if __name__ == "__main__":
    check_report()
