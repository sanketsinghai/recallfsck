"""Observe a pinned, disposable Open WebUI through its real APIs and pgvector index.

This is an author-run application integration, not independent participant feedback.
No production target or real document is supported by this recipe.
"""

import argparse
import json
import subprocess
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from recallfsck.reporting import write_reports
from recallfsck.stores import Document, ordered
from recallfsck.suite import differences


def run(url, container, output):
    token = None
    history, cases = [], []

    def request(method, path, payload=None, raw=None, content_type="application/json"):
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(url.rstrip("/") + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=90) as response:
                status, result = response.status, json.load(response)
        except HTTPError as error:
            status, result = error.code, json.load(error)
        history.append({"method": method, "path": path, "http_status": status})
        return status, result

    status, version = request("GET", "/api/version")
    if status != 200 or version.get("version") != "0.12.4":
        raise ValueError("Trial requires the pinned Open WebUI v0.12.4 container")
    status, auth = request("POST", "/api/v1/auths/signin", {"email": "admin@localhost", "password": "admin"})
    if status != 200 or not auth.get("token"):
        raise ValueError("Disposable WEBUI_AUTH=False instance did not initialize its synthetic account")
    token = auth["token"]
    original = Document(
        text="RecallFSCK synthetic observatory access code is AMBER-17; trial " + uuid.uuid4().hex
    )
    replacement = replace(
        original, revision=2, text="RecallFSCK synthetic observatory access code is VIOLET-29."
    )
    file_id = None

    def index_rows():
        # Inspect the application's own vector store, not a recreated test index.
        code = (
            "import json; from open_webui.retrieval.vector.factory import get_vector_db_client; "
            "client=get_vector_db_client(); name=" + repr("file-" + file_id) + "; "
            "value=client.query(collection_name=name,filter={}) if client.has_collection(collection_name=name) else None; "
            "print('RECALLFSCK_INDEX='+json.dumps(value.model_dump() if value is not None else {'documents':[]}))"
        )
        result = subprocess.run(
            ["docker", "exec", container, "python", "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        lines = [line for line in result.stdout.splitlines() if line.startswith("RECALLFSCK_INDEX=")]
        if not lines:
            raise ValueError("No observed application index result")
        return records(json.loads(lines[-1].split("=", 1)[1]))

    def records(result):
        rows = []
        for batch in result.get("documents") or []:
            for text in batch if isinstance(batch, list) else [batch]:
                rows.append(json.loads(text))
        return ordered(rows)

    def check(name, expected, observed, started, additional=None):
        failures = differences(expected, observed)
        case = {
            "backend": "openwebui-pgvector",
            "application": "open-webui@v0.12.4",
            "worker": "actual-api",
            "scenario": name,
            "status": "FAIL" if failures else "PASS",
            "duration_seconds": time.perf_counter() - started,
            "first_divergence": failures[0] if failures else None,
            "checks": [{"expected": expected, "observations": observed, "failures": failures}],
            "history": list(history),
            "scope": "Actual pinned Open WebUI ingestion/retrieval/index APIs with synthetic documents and deterministic local embeddings; no tenant or controlled-race claim.",
        }
        if additional:
            case.update(additional)
        cases.append(case)
        print(case["status"], name)

    def observe(expected):
        status, result = request(
            "POST",
            "/api/v1/retrieval/query/doc",
            {
                "collection_name": "file-" + file_id,
                "query": "observatory access code",
                "k": 20,
                "hybrid": False,
            },
        )
        if status != 200:
            raise ValueError(f"Application retrieval failed with HTTP {status}")
        return [
            {"path": "application.retrieve", "tenant": "alpha", "model": "v1", "rows": records(result)},
            {"path": "index.scan", "rows": index_rows()},
        ]

    try:
        started = time.perf_counter()
        boundary = "recallfsck" + uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recallfsck-synthetic.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n" + json.dumps(asdict(original)) + f"\r\n--{boundary}--\r\n"
        ).encode()
        status, result = request(
            "POST",
            "/api/v1/files/?process=true&process_in_background=false",
            raw=body,
            content_type="multipart/form-data; boundary=" + boundary,
        )
        if status != 200 or not result.get("id"):
            raise ValueError(f"Application ingestion failed with HTTP {status}: {str(result)[:300]}")
        file_id = result["id"]
        check("create-and-retrieve", [asdict(original)], observe(original), started)

        started = time.perf_counter()
        status, result = request(
            "POST",
            f"/api/v1/files/{file_id}/data/content/update",
            {"content": json.dumps(asdict(replacement))},
        )
        if status != 200:
            raise ValueError(f"Application update failed with HTTP {status}")
        check("replace-no-stale-revision", [asdict(replacement)], observe(replacement), started)

        started = time.perf_counter()
        status, _ = request(
            "POST",
            "/api/v1/retrieval/process/file",
            {"file_id": file_id, "content": json.dumps(asdict(replacement))},
        )
        if status != 200:
            raise ValueError(f"Repeated processing failed with HTTP {status}")
        check("repeat-index-no-duplicates", [asdict(replacement)], observe(replacement), started)

        started = time.perf_counter()
        status, _ = request("DELETE", f"/api/v1/files/{file_id}")
        if status != 200:
            raise ValueError(f"Application deletion failed with HTTP {status}")
        status, _ = request("GET", f"/api/v1/files/{file_id}")
        query_status, _ = request(
            "POST",
            "/api/v1/retrieval/query/doc",
            {"collection_name": "file-" + file_id, "query": "observatory access code", "k": 20},
        )
        check(
            "delete-removes-index-records",
            [],
            [{"path": "index.scan", "rows": index_rows()}],
            started,
            {
                "file_api_status_after_delete": status,
                "query_status_after_delete": query_status,
                "retrieval_note": "A denied query is not interpreted as index absence; the application's own index was inspected separately.",
            },
        )
        if status != 404:
            cases[-1]["status"] = "FAIL"
            cases[-1]["first_divergence"] = {
                "path": "application.file",
                "expected": "HTTP 404",
                "observed": status,
            }

        image = subprocess.check_output(
            ["docker", "inspect", container, "--format", "{{.Config.Image}}"], text=True
        ).strip()
        digests = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"], text=True
            )
        )
        receipt = {
            "application": "Open WebUI",
            "version": version,
            "repository": "https://github.com/open-webui/open-webui",
            "source_commit": "33c1978d5bad52a31df75ea55143025dfad18d16",
            "image": image,
            "image_digests": digests,
            "execution": "Author-run real application trial, not independent participant validation",
            "embedding_provider": "Deterministic local 64-dimensional synthetic provider; no external model or answer-quality test",
            "covered": [case["scenario"] for case in cases],
            "not_tested": [
                "Tenant isolation (authentication disabled in isolated instance)",
                "Controlled indexing races (no pause/resume hooks installed)",
                "Embedding migration",
                "LLM answer quality",
                "Long-term deletion absence",
            ],
            "application_source_changes": "None; unmodified upstream container and its actual APIs/index were used",
            "results": [{"scenario": case["scenario"], "status": case["status"]} for case in cases],
        }
        write_reports(cases, output, context={"command": "openwebui-trial"})
        Path(output, "application-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        assert all(case["status"] == "PASS" for case in cases), receipt
        return receipt
    finally:
        if file_id:
            request("DELETE", f"/api/v1/files/{file_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18080")
    parser.add_argument("--container", default="recallfsck-openwebui")
    parser.add_argument("--output", type=Path, default=Path("report/openwebui"))
    args = parser.parse_args()
    try:
        run(args.url, args.container, args.output)
    except Exception as error:
        write_reports(
            [
                {
                    "backend": "openwebui-pgvector",
                    "application": "open-webui@v0.12.4",
                    "worker": "actual-api",
                    "scenario": "trial-execution",
                    "status": "ERROR",
                    "error": {
                        "type": type(error).__name__,
                        "message": "Application trial did not complete; check disposable service configuration and API availability.",
                    },
                }
            ],
            args.output,
            context={"command": "openwebui-trial"},
        )
        raise


if __name__ == "__main__":
    main()
