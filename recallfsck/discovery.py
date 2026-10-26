"""Hypothesis search and shrinking of actual failing application schedules."""

import asyncio

from .suite import run_sequence, validate_schedule


def discover(factory, worker, examples=50, **options):
    from hypothesis import HealthCheck, errors, find, settings
    from hypothesis import strategies as st

    if not isinstance(examples, int) or not 1 <= examples <= 10000:
        raise ValueError("examples must be in 1..10000")
    # Balanced race blocks allow Hypothesis to delete blocks and irrelevant writes
    # while retaining deterministic synchronization rather than sleep-based races.
    blocks = st.sampled_from(
        [
            ["insert"],
            ["insert_beta"],
            ["delete"],
            ["migrate"],
            ["insert", "replace"],
            ["insert", "metadata"],
            ["insert", "start_index", "delete", "resume_index"],
            ["insert", "start_index", "replace", "resume_index"],
            ["insert", "start_index", "migrate", "resume_index"],
        ]
    )
    strategy = st.lists(blocks, min_size=1, max_size=8).map(lambda groups: sum(groups, []) + ["observe"])

    def fails(schedule):
        validate_schedule(schedule)
        return (
            asyncio.run(run_sequence(factory, worker, "generated", schedule, **options))["status"] == "FAIL"
        )

    try:
        return find(
            strategy,
            fails,
            settings=settings(
                max_examples=examples,
                deadline=None,
                database=None,
                derandomize=True,
                suppress_health_check=[HealthCheck.too_slow],
            ),
        )
    except errors.NoSuchExample:
        return None
