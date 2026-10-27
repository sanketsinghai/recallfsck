"""Install one exact wheel in a clean environment and exercise its public behavior."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from xml.etree.ElementTree import parse


def verify(wheel, output):
    wheel, output = wheel.resolve(), output.resolve()
    root = Path(__file__).resolve().parent.parent
    expected_version = wheel.name.split("-")[1]
    with tempfile.TemporaryDirectory(prefix="recallfsck-wheel-") as temporary:
        folder = Path(temporary)
        venv.create(folder / "env", with_pip=True)
        python = folder / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)

        def run(*args, expected=0):
            result = subprocess.run([str(python), *map(str, args)], cwd=folder, env=env)
            if result.returncode != expected:
                raise AssertionError(f"{args}: exit {result.returncode}, expected {expected}")

        run("-m", "pip", "install", wheel)
        run(
            "-c",
            "import recallfsck; from pathlib import Path; from importlib.metadata import version; "
            f"assert version('recallfsck') == {expected_version!r}; "
            f"assert Path(recallfsck.__file__).is_relative_to({str(folder)!r}); "
            "print('Exact installed wheel:', recallfsck.__file__)",
        )
        run(root / "qa/test_recallfsck_external.py", "--output", output / "seven-case")
        run(root / "qa/test_recallfsck_reporting.py")
        run("-m", "recallfsck", "demo", "--output", output / "demo")
        run("-m", "recallfsck", "test", "--worker", "fixed", "--output", output / "fixed")
        run(
            "-m",
            "recallfsck",
            "replay",
            output / "demo/buggy-delete-during-index.json",
            "--output",
            output / "replay",
            expected=1,
        )
        run(
            "-m",
            "recallfsck",
            "demo",
            "--app",
            "recallfsck.demo_http:create_application",
            "--output",
            output / "http",
        )
        run("-m", "pip", "check")
        manifest = json.loads((output / "demo/report.json").read_text())
        assert manifest["counts"] == {"total": 20, "pass": 17, "fail": 3, "error": 0}
        assert manifest["package_version"] == expected_version
        xml = parse(output / "demo/junit.xml").getroot()
        assert xml.attrib["tests"] == "20" and xml.attrib["failures"] == "3"
        assert all(
            node.find("properties/property[@name='application']") is not None
            for node in xml.findall("testcase")
        )
        assert (output / "demo/index.html").exists()
        receipt = {
            "wheel": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "version": expected_version,
            "python": sys.version,
            "status": "PASS",
            "seven_case_qa": "2 PASS / 5 detected FAIL; all seven expectations met",
            "checks": [
                "clean import",
                "report regression",
                "demo",
                "fixed suite",
                "failing replay",
                "HTTP demo",
                "JUnit",
                "HTML",
                "JSON manifest",
                "dependency check",
            ],
        }
        (output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print("Exact-wheel verification passed:", wheel.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("report/wheel"))
    args = parser.parse_args()
    verify(args.wheel, args.output)


if __name__ == "__main__":
    main()
