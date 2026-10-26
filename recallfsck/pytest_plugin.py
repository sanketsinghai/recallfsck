"""Opt-in pytest fixture; no tests or database mutations on plugin import."""

import asyncio

import pytest

from .stores import store_factory
from .suite import SCENARIOS, run_sequence


def pytest_addoption(parser):
    group = parser.getgroup("recallfsck")
    group.addoption(
        "--recallfsck-backend", default="sqlite", choices=["sqlite", "qdrant", "chroma", "pgvector"]
    )
    group.addoption("--recallfsck-url", default=None)


@pytest.fixture
def recallfsck_runner(request):
    factory = store_factory(
        request.config.getoption("--recallfsck-backend"), request.config.getoption("--recallfsck-url")
    )

    def run(scenario="delete-during-index", worker="fixed", **kwargs):
        return asyncio.run(run_sequence(factory, worker, scenario, SCENARIOS[scenario], **kwargs))

    return run
