"""One controlled schedule, real backend observations, no timing sleeps."""

import asyncio
from dataclasses import dataclass, field

SCHEDULES = {
    "create": ["insert", "observe"],
    "delete": ["insert", "delete", "observe"],
    "delete-during-index": ["insert", "start_index", "delete", "resume_index", "observe"],
}


@dataclass
class ReferenceState:
    live: set = field(default_factory=set)

    def apply(self, operation, doc_id):
        if operation == "insert":
            self.live.add(doc_id)
        elif operation == "delete":
            self.live.discard(doc_id)


class Pipeline:
    """The fixed fixture serializes deletion and a generation-checked commit.

    This lock is local to this fixture, not a distributed coordination solution.
    Retrieval deliberately queries the index without hiding tombstoned records.
    """

    def __init__(self, index, fixed):
        self.index, self.fixed = index, fixed
        self.generation = 0
        self.live = False
        self.lock = asyncio.Lock()

    async def insert(self):
        async with self.lock:
            self.generation += 1
            self.live = True
            self.index.upsert(42, "synthetic knowledge")

    async def delete(self):
        async with self.lock:
            self.generation += 1
            self.live = False
            self.index.delete(42)

    async def run_indexing(self, paused, resume):
        generation = self.generation
        paused.set()
        await resume.wait()
        async with self.lock:
            if not self.fixed or (self.live and generation == self.generation):
                self.index.upsert(42, "synthetic knowledge")

    def retrieve(self):
        return self.index.search()


async def run_case(factory, worker, name, schedule=None):
    if worker not in ("buggy", "fixed"):
        raise ValueError("Unknown worker")
    if not isinstance(name, str) or name not in SCHEDULES:
        raise ValueError("Unknown scenario")
    schedule = SCHEDULES[name] if schedule is None else schedule
    if schedule != SCHEDULES[name]:
        raise ValueError("Unsupported schedule: replay requires a known controlled schedule")
    index = factory()
    history, observations = [], []
    task = None
    paused, resume = asyncio.Event(), asyncio.Event()
    model = ReferenceState()
    pipeline = Pipeline(index, worker == "fixed")
    try:
        for operation in schedule:
            if operation == "insert":
                await pipeline.insert()
            elif operation == "delete":
                await pipeline.delete()
            elif operation == "start_index":
                task = asyncio.create_task(pipeline.run_indexing(paused, resume))
                await asyncio.wait_for(paused.wait(), timeout=5)
            elif operation == "resume_index":
                resume.set()
                await asyncio.wait_for(task, timeout=5)
            elif operation == "observe":
                observations = [
                    {"path": "application.retrieve", "ids": pipeline.retrieve()},
                    {"path": "index.inspect", "ids": index.inspect()},
                ]
            model.apply(operation, 42)
            history.append(
                {"step": len(history) + 1, "operation": operation, "expected_live_ids": sorted(model.live)}
            )
        expected = sorted(model.live)
        failures = [obs for obs in observations if obs["ids"] != expected]
        return {
            "scenario": name,
            "worker": worker,
            "schedule": schedule,
            "status": "FAIL" if failures else "PASS",
            "history": history,
            "expected_live_ids": expected,
            "observations": observations,
            "first_divergence": failures[0] if failures else None,
        }
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        index.close()
