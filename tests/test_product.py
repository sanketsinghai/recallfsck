import asyncio
import json
import os
from dataclasses import asdict
from xml.etree.ElementTree import parse

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from recallfsck.discovery import discover
from recallfsck.product_cli import main
from recallfsck.stores import Document, SQLiteStore, store_factory
from recallfsck.suite import SCENARIOS, minimize, run_sequence

FAST = dict(consistency_seconds=0, monitor_seconds=0, poll_seconds=0.001)


@pytest.mark.parametrize("name", SCENARIOS)
def test_fixed_all_scenarios(name):
    case = asyncio.run(run_sequence(SQLiteStore, "fixed", name, SCENARIOS[name], **FAST))
    assert case["status"] == "PASS", case["first_divergence"]
    assert len(case["checks"][-1]["observations"]) == 7


@pytest.mark.parametrize(
    ("worker", "name"),
    [
        ("buggy", "delete-during-index"),
        ("buggy", "update-during-index"),
        ("buggy", "migration-during-index"),
        ("stale-update", "update"),
        ("stale-metadata", "metadata"),
        ("tenant-leak", "isolation"),
        ("duplicate", "idempotency"),
        ("migration-loss", "migration"),
    ],
)
def test_oracle_detects_each_injected_bug(worker, name):
    case = asyncio.run(run_sequence(SQLiteStore, worker, name, SCENARIOS[name], **FAST))
    assert case["status"] == "FAIL"
    assert case["first_divergence"]


def test_hypothesis_discovers_and_shrinks_actual_race():
    sequence = discover(SQLiteStore, "buggy", examples=100, **FAST)
    assert sequence is not None
    case = asyncio.run(run_sequence(SQLiteStore, "buggy", "generated", sequence, **FAST))
    assert case["status"] == "FAIL"
    assert "start_index" in sequence and "resume_index" in sequence


def test_deletion_minimizer_and_reexecution():
    sequence = ["insert_beta", "insert", "insert", "start_index", "delete", "resume_index", "observe"]
    artifact = {"worker": "buggy", "scenario": "generated", "schedule": sequence}
    result = asyncio.run(minimize(SQLiteStore, artifact, **FAST))
    assert result["status"] == "FAIL"
    assert len(result["schedule"]) < len(sequence)
    assert result["schedule"] == SCENARIOS["delete-during-index"]


@given(st.lists(st.sampled_from(["insert", "insert_beta", "delete", "migrate"]), min_size=1, max_size=30))
@settings(max_examples=60, deadline=None)
def test_model_matches_fixed_application_for_generated_sequences(operations):
    result = asyncio.run(run_sequence(SQLiteStore, "fixed", "property", operations + ["observe"], **FAST))
    assert result["status"] == "PASS", result["first_divergence"]


def test_eventual_convergence_and_timeout():
    class Delayed(SQLiteStore):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def scan(self):
            self.reads += 1
            return [] if self.reads < 3 else super().scan()

    case = asyncio.run(
        run_sequence(
            Delayed,
            "fixed",
            "create",
            SCENARIOS["create"],
            consistency_seconds=0.2,
            monitor_seconds=0,
            poll_seconds=0.001,
        )
    )
    assert case["status"] == "PASS"
    assert case["checks"][0]["timing"]["attempts"] == 3
    case = asyncio.run(run_sequence(Delayed, "fixed", "create", SCENARIOS["create"], **FAST))
    assert case["status"] == "FAIL"


def test_monitor_catches_later_resurrection():
    class Reappearing(SQLiteStore):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def scan(self):
            self.reads += 1
            if self.reads >= 2:
                return [asdict(Document())]
            return super().scan()

    result = asyncio.run(
        run_sequence(
            Reappearing,
            "fixed",
            "delete",
            SCENARIOS["delete"],
            consistency_seconds=0,
            monitor_seconds=0.05,
            poll_seconds=0.001,
        )
    )
    assert result["status"] == "FAIL"
    assert result["checks"][0]["timing"]["attempts"] == 2


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True, "1"])
def test_invalid_timing_rejected(value):
    with pytest.raises(ValueError):
        asyncio.run(
            run_sequence(SQLiteStore, "fixed", "create", SCENARIOS["create"], consistency_seconds=value)
        )


@pytest.mark.parametrize(
    "sequence",
    [
        [],
        ["observe", "start_index"],
        ["insert", "start_index", "observe"],
        ["resume_index", "observe"],
        ["replace", "observe"],
        ["insert"],
        [None],
    ],
)
def test_invalid_schedules_never_mutate(sequence):
    def forbidden():
        pytest.fail("invalid schedule created a store")

    with pytest.raises(ValueError):
        asyncio.run(run_sequence(forbidden, "fixed", "invalid", sequence, **FAST))


def test_cli_config_demo_replay_minimize_and_reports(tmp_path):
    config = tmp_path / "config.yaml"
    report = tmp_path / "evidence"
    assert main(["init", "--config", str(config)]) == 0
    assert main(["init", "--config", str(config)]) == 2
    assert main(["test", "--config", str(config), "--output", str(report), "--monitor-seconds", "0"]) == 0
    assert (
        main(["demo", "--output", str(report), "--monitor-seconds", "0", "--consistency-seconds", "0"]) == 0
    )
    summary = json.loads((report / "summary.json").read_text())
    assert len(summary) == 20
    assert sum(case["status"] == "FAIL" for case in summary) == 3
    assert parse(report / "junit.xml").getroot().attrib["failures"] == "3"
    artifact = str(report / "buggy-delete-during-index.json")
    assert main(["replay", artifact, "--output", str(tmp_path / "replayed")]) == 1
    assert main(["minimize", artifact, "--output", str(tmp_path / "minimal")]) == 1
    assert "RecallFSCK evidence" in (report / "index.html").read_text()


def test_cli_backend_errors_not_passes(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("backend: qdrant\nurl: http://127.0.0.1:1\nscenarios: [create]\n")
    assert main(["test", "--config", str(config), "--output", str(tmp_path)]) == 2
    report = json.loads((tmp_path / "summary.json").read_text())
    assert report[0]["status"] == "ERROR"
    assert parse(tmp_path / "junit.xml").getroot().attrib["errors"] == "1"


def test_pytest_fixture(recallfsck_runner):
    assert recallfsck_runner("delete-during-index", **FAST)["status"] == "PASS"


@pytest.mark.parametrize("backend", ["qdrant", "chroma", "pgvector"])
def test_external_backends(backend):
    if backend == "chroma":
        pytest.importorskip("chromadb")
        url = None
    else:
        url = os.environ.get("RECALLFSCK_" + backend.upper() + "_URL")
        if not url:
            pytest.skip("requires disposable database endpoint")
    native_factory = store_factory(backend, url)
    stores = []

    def factory():
        store = native_factory()
        stores.append(store)
        return store

    for worker in ("fixed", "buggy"):
        for name, schedule in SCENARIOS.items():
            result = asyncio.run(run_sequence(factory, worker, name, schedule, **FAST))
            expected = (
                "FAIL"
                if worker == "buggy"
                and name in ("delete-during-index", "update-during-index", "migration-during-index")
                else "PASS"
            )
            assert result["status"] == expected, (backend, worker, name, result["first_divergence"])
    if backend == "qdrant":
        from urllib.error import HTTPError

        for store in stores:
            with pytest.raises(HTTPError) as error:
                store.request("GET", "")
            assert error.value.code == 404
    elif backend == "chroma":
        remaining = {collection.name for collection in stores[0].client.list_collections()}
        assert all(store.name not in remaining for store in stores)
    else:
        import psycopg

        with psycopg.connect(url) as conn:
            for store in stores:
                assert conn.execute("SELECT to_regclass(%s)", (store.name,)).fetchone()[0] is None


@pytest.mark.parametrize("backend", ["qdrant", "chroma", "pgvector"])
def test_migration_detects_wrong_real_vectors_even_when_metadata_matches(backend):
    if backend == "chroma":
        pytest.importorskip("chromadb")
        url = None
    else:
        url = os.environ.get("RECALLFSCK_" + backend.upper() + "_URL")
        if not url:
            pytest.skip("requires disposable database endpoint")
    native_factory = store_factory(backend, url)

    class WrongVector(Document):
        @property
        def vector(self):
            return [1.0, 0.0]

    def factory():
        store = native_factory()
        native_upsert = store.upsert
        store.upsert = lambda document: native_upsert(WrongVector(**asdict(document)))
        return store

    case = asyncio.run(run_sequence(factory, "fixed", "migration", SCENARIOS["migration"], **FAST))
    assert case["status"] == "FAIL"
    assert case["first_divergence"]["path"] == "application.retrieve"
    assert case["first_divergence"]["model"] == "v2"


def test_http_application_real_transport():
    from examples.http_application import create_application

    for worker, expected in (("fixed", "PASS"), ("buggy", "FAIL")):
        result = asyncio.run(
            run_sequence(
                SQLiteStore,
                worker,
                "delete-during-index",
                SCENARIOS["delete-during-index"],
                app_factory=create_application,
                **FAST,
            )
        )
        assert result["status"] == expected


def test_failed_index_hook_propagates_and_releases_resources():
    from recallfsck.suite import FixtureApplication

    closed = []

    class Broken(FixtureApplication):
        async def index(self, *args):
            raise OSError("synthetic hook failure")

        def close(self):
            closed.append(True)

    with pytest.raises(OSError, match="synthetic hook failure"):
        asyncio.run(
            run_sequence(
                SQLiteStore,
                "fixed",
                "delete-during-index",
                SCENARIOS["delete-during-index"],
                app_factory=Broken,
                **FAST,
            )
        )
    assert closed == [True]


def test_completed_hook_cannot_pass_as_a_controlled_race():
    from recallfsck.suite import FixtureApplication

    class Invalid(FixtureApplication):
        async def index(self, tenant, doc_id, paused, resume):
            paused.set()

    with pytest.raises(RuntimeError, match="completed before"):
        asyncio.run(
            run_sequence(
                SQLiteStore,
                "fixed",
                "delete-during-index",
                SCENARIOS["delete-during-index"],
                app_factory=Invalid,
                **FAST,
            )
        )


def test_report_escapes_external_content(tmp_path):
    from recallfsck.reporting import write_reports

    write_reports(
        [
            {
                "worker": "fixed",
                "scenario": "create",
                "backend": "sqlite",
                "status": "FAIL",
                "first_divergence": {"text": "<script>alert(1)</script>"},
            }
        ],
        tmp_path,
    )
    html = (tmp_path / "index.html").read_text()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_real_langchain_chroma_integration():
    pytest.importorskip("langchain_chroma")
    from recallfsck.integrations.langchain_chroma import create_application

    factory = store_factory("chroma")
    for worker in ("fixed", "buggy"):
        for name, schedule in SCENARIOS.items():
            case = asyncio.run(
                run_sequence(factory, worker, name, schedule, app_factory=create_application, **FAST)
            )
            expected = (
                "FAIL"
                if worker == "buggy"
                and name in ("delete-during-index", "update-during-index", "migration-during-index")
                else "PASS"
            )
            assert case["status"] == expected, (worker, name, case["first_divergence"])


def test_input_errors_produce_standard_error_evidence(tmp_path):
    config = tmp_path / "invalid.yaml"
    config.write_text("backend: sqlite\nscenarios: [not-a-scenario]\n")
    assert main(["test", "--config", str(config), "--output", str(tmp_path)]) == 2
    manifest = json.loads((tmp_path / "report.json").read_text())
    assert manifest["counts"] == {"total": 1, "pass": 0, "fail": 0, "error": 1}
    assert "hint" in manifest["cases"][0]["error"]


def test_diagnostic_redacts_driver_url_and_includes_safe_http_status():
    from urllib.error import HTTPError

    from recallfsck.product_cli import diagnostic

    result = diagnostic(
        HTTPError("https://user:secret@example.com", 503, "private token secret", {}, None), "qdrant"
    )
    assert "503" in result["hint"]
    assert "secret" not in json.dumps(result)
