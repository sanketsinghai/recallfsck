"""State model, controlled application fixture, convergence and bounded monitoring."""

import asyncio
import math
import time
from dataclasses import asdict, replace

from .stores import Document, ordered

SCENARIOS = {
    "create": ["insert", "observe"],
    "update": ["insert", "replace", "observe"],
    "metadata": ["insert", "metadata", "observe"],
    "delete": ["insert", "delete", "observe"],
    "idempotency": ["insert", "insert", "observe", "delete", "delete", "observe"],
    "isolation": ["insert", "insert_beta", "observe", "delete", "observe"],
    "delete-during-index": ["insert", "start_index", "delete", "resume_index", "observe"],
    "update-during-index": ["insert", "start_index", "replace", "resume_index", "observe"],
    "migration": ["insert", "insert_beta", "migrate", "observe"],
    "migration-during-index": ["insert", "start_index", "migrate", "resume_index", "observe"],
}
WORKERS = ("fixed", "buggy", "stale-update", "tenant-leak", "migration-loss", "duplicate", "stale-metadata")
OPERATIONS = set(sum(SCENARIOS.values(), []))
SCOPE = (
    "Observed synthetic documents on these retrieval paths, schedules and time windows only. "
    "No physical erasure, distributed race safety or arbitrary embedding-model guarantee."
)


def validate_schedule(schedule):
    if not isinstance(schedule, list) or not 1 <= len(schedule) <= 200:
        raise ValueError("Schedule must contain 1–200 operations")
    pending, live = False, False
    for operation in schedule:
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError("Unknown operation")
        if operation == "start_index":
            if pending or not live:
                raise ValueError("Index start requires a live document and no pending job")
            pending = True
        elif operation == "resume_index":
            if not pending:
                raise ValueError("No indexing job to resume")
            pending = False
        elif operation in ("replace", "metadata") and not live:
            raise ValueError("Replacement requires a live document")
        if operation == "insert":
            live = True
        elif operation == "delete":
            live = False
    if pending or schedule[-1] != "observe":
        raise ValueError("Schedule must finish with an observation and no paused job")


class ReferenceModel:
    def __init__(self):
        self.documents = {}

    def apply(self, operation):
        if operation == "insert":
            self.documents["alpha:42"] = Document()
        elif operation == "insert_beta":
            self.documents["beta:42"] = Document(tenant="beta", text="private beta fact")
        elif operation == "replace":
            self.documents["alpha:42"] = replace(
                self.documents["alpha:42"], text="replacement fact", revision=2
            )
        elif operation == "metadata":
            self.documents["alpha:42"] = replace(self.documents["alpha:42"], revision=2)
        elif operation == "delete":
            self.documents.pop("alpha:42", None)
        elif operation == "migrate":
            self.documents = {key: replace(doc, model="v2") for key, doc in self.documents.items()}

    def rows(self):
        return ordered([asdict(doc) for doc in self.documents.values()])


class FixtureApplication:
    """Small application adapter; locking protects check+commit, not just check."""

    def __init__(self, store, worker="fixed"):
        self.store, self.worker = store, worker
        self.documents, self.generations = {}, {}
        self.lock = asyncio.Lock()

    async def put(self, document):
        async with self.lock:
            previous = self.documents.get(document.key)
            self.generations[document.key] = self.generations.get(document.key, 0) + 1
            self.documents[document.key] = document
            if previous and self.worker == "stale-update":
                return
            if previous and self.worker == "stale-metadata":
                document = replace(document, revision=previous.revision)
            self.store.upsert(document)
            if previous and self.worker == "duplicate":
                self.store.upsert(replace(document, id=43))

    async def delete(self, tenant, doc_id):
        async with self.lock:
            key = f"{tenant}:{doc_id}"
            self.generations[key] = self.generations.get(key, 0) + 1
            self.documents.pop(key, None)
            self.store.delete(tenant, doc_id)

    async def migrate(self):
        async with self.lock:
            for key, doc in list(self.documents.items()):
                self.generations[key] += 1
                updated = replace(doc, model="v2")
                self.documents[key] = updated
                if self.worker == "migration-loss":
                    self.store.delete(doc.tenant, doc.id)
                else:
                    self.store.upsert(updated)

    async def index(self, tenant, doc_id, paused, resume):
        key = f"{tenant}:{doc_id}"
        captured, generation = self.documents[key], self.generations[key]
        paused.set()
        await resume.wait()
        async with self.lock:
            if self.worker == "buggy" or (key in self.documents and self.generations[key] == generation):
                self.store.upsert(captured)

    def retrieve(self, tenant, model):
        if self.worker == "tenant-leak":
            # An intentionally broken authorization filter, exercised by the same oracle.
            return ordered(self.store.query("alpha", model) + self.store.query("beta", model))
        return self.store.query(tenant, model)


def differences(expected, observations):
    failures = []
    for observation in observations:
        wanted = (
            expected
            if observation["path"] == "index.scan"
            else [
                row
                for row in expected
                if row["tenant"] == observation["tenant"] and row["model"] == observation["model"]
            ]
        )
        if observation["rows"] != wanted:
            failures.append(
                {
                    "path": observation["path"],
                    "tenant": observation.get("tenant"),
                    "model": observation.get("model"),
                    "expected": wanted,
                    "observed": observation["rows"],
                }
            )
    return failures


async def observe(store, app, expected, consistency_seconds, monitor_seconds, poll_seconds):
    started = time.monotonic()
    deadline = started + consistency_seconds
    stable_since = None
    attempts = 0
    samples = []
    # Convergence deadline and a separate continuous observation window. Neither
    # implies that a deletion remains absent after this finite experiment ends.
    while True:
        attempts += 1
        observations = [{"path": "index.scan", "rows": ordered(store.scan())}]
        for tenant in ("alpha", "beta", "outsider"):
            for model in ("v1", "v2"):
                observations.append(
                    {
                        "path": "application.retrieve",
                        "tenant": tenant,
                        "model": model,
                        "rows": ordered(app.retrieve(tenant, model)),
                    }
                )
        failures = differences(expected, observations)
        now = time.monotonic()
        if len(samples) < 20:
            samples.append({"elapsed_seconds": now - started, "matching": not failures})
        if failures:
            if stable_since is not None or now >= deadline:
                return (
                    observations,
                    failures,
                    {"attempts": attempts, "samples": samples, "elapsed_seconds": now - started},
                )
        else:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= monitor_seconds:
                return (
                    observations,
                    [],
                    {"attempts": attempts, "samples": samples, "elapsed_seconds": now - started},
                )
        await asyncio.sleep(poll_seconds)


async def run_sequence(
    factory,
    worker,
    scenario,
    schedule,
    *,
    consistency_seconds=0.1,
    monitor_seconds=0.02,
    poll_seconds=0.01,
    app_factory=FixtureApplication,
):
    if worker not in WORKERS:
        raise ValueError("Unknown worker")
    validate_schedule(schedule)
    for value in (consistency_seconds, monitor_seconds, poll_seconds):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            or value > 60
        ):
            raise ValueError("Timing values must be finite numbers from 0 to 60")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    store = factory()
    history, checks = [], []
    pending = None
    model = ReferenceModel()
    app = None
    try:
        app = app_factory(store, worker)
        for operation in schedule:
            # Inputs are constructed independently of the reference model.
            if operation == "insert":
                await app.put(Document())
            elif operation == "insert_beta":
                await app.put(Document(tenant="beta", text="private beta fact"))
            elif operation in ("replace", "metadata"):
                # The command updates known synthetic source data, not observed index state.
                doc = model.documents["alpha:42"]
                await app.put(
                    replace(doc, revision=2, text="replacement fact" if operation == "replace" else doc.text)
                )
            elif operation == "delete":
                await app.delete("alpha", 42)
            elif operation == "migrate":
                await app.migrate()
            elif operation == "start_index":
                paused, resume = asyncio.Event(), asyncio.Event()
                pending = asyncio.create_task(app.index("alpha", 42, paused, resume))
                pause_waiter = asyncio.create_task(paused.wait())
                try:
                    done, _ = await asyncio.wait(
                        {pending, pause_waiter}, timeout=5, return_when=asyncio.FIRST_COMPLETED
                    )
                    if pending in done:
                        await pending
                        raise RuntimeError("Index hook completed before the scheduler resumed it")
                    if pause_waiter not in done:
                        raise TimeoutError("Index hook did not reach its pause point")
                finally:
                    pause_waiter.cancel()
                    await asyncio.gather(pause_waiter, return_exceptions=True)
            elif operation == "resume_index":
                resume.set()
                await asyncio.wait_for(pending, 5)
                pending = None
            model.apply(operation)
            history.append({"step": len(history) + 1, "operation": operation, "expected": model.rows()})
            if operation == "observe":
                observations, failures, timing = await observe(
                    store, app, model.rows(), consistency_seconds, monitor_seconds, poll_seconds
                )
                checks.append(
                    {
                        "step": len(history),
                        "expected": model.rows(),
                        "observations": observations,
                        "failures": failures,
                        "timing": timing,
                    }
                )
        failures = [failure for check in checks for failure in check["failures"]]
        return {
            "schema_version": 2,
            "scenario": scenario,
            "worker": worker,
            "schedule": schedule,
            "status": "FAIL" if failures else "PASS",
            "history": history,
            "checks": checks,
            "first_divergence": failures[0] if failures else None,
            "scope": SCOPE,
            "settings": {
                "consistency_seconds": consistency_seconds,
                "monitor_seconds": monitor_seconds,
                "poll_seconds": poll_seconds,
            },
        }
    finally:
        if pending is not None:
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        try:
            if app is not None and hasattr(app, "close"):
                app.close()
        finally:
            store.close()


async def minimize(factory, artifact, **options):
    """Deletion-based shrinking, preserving the original divergence category.

    Produces a 1-minimal valid subsequence, not a globally shortest schedule.
    Every accepted candidate executes against a fresh disposable store.
    """
    original = await run_sequence(
        factory, artifact["worker"], artifact["scenario"], artifact["schedule"], **options
    )
    if original["status"] != "FAIL":
        raise ValueError("The supplied schedule does not reproduce a failure")
    target = original["first_divergence"]
    schedule = list(artifact["schedule"])
    changed = True
    while changed:
        changed = False
        for offset in range(len(schedule)):
            candidate = schedule[:offset] + schedule[offset + 1 :]
            try:
                validate_schedule(candidate)
            except ValueError:
                continue
            result = await run_sequence(
                factory, artifact["worker"], artifact["scenario"], candidate, **options
            )
            divergence = result["first_divergence"]
            if divergence and all(
                divergence.get(key) == target.get(key) for key in ("path", "tenant", "model")
            ):
                schedule = candidate
                changed = True
                break
    result = await run_sequence(factory, artifact["worker"], artifact["scenario"], schedule, **options)
    result["minimization"] = {
        "original_steps": len(artifact["schedule"]),
        "minimized_steps": len(schedule),
        "method": "1-minimal valid deletion subsequence; same divergence path",
    }
    return result
