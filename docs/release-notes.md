# RecallFSCK 0.2.0rc1

Stateful lifecycle integrity checks for RAG indexes, with replayable evidence.

Implemented:
- Ten lifecycle scenarios: create, update, metadata, delete, idempotency,
  isolation, delete/index, update/index, migration and migration/index.
- Actual Qdrant, Chroma and pgvector adapters, plus a zero-service SQLite demo.
- Real LangChain/Chroma ingestion and retrieval integration.
- Controlled scheduling, finite consistency windows, independent reference state.
- Hypothesis discovery/shrinking, JSON replay, minimization and pytest integration.
- JSON/HTML/JUnit evidence and a runnable local HTTP application.

Install the attached wheel using Python 3.11+:

```sh
python -m pip install recallfsck-0.2.0rc1-py3-none-any.whl
recallfsck demo
```

For all integrations, install `.[all,test]` from the source checkout.
The demo intentionally reports three buggy-worker failures and ten corrected-worker
passes. The other seven buggy-worker cases pass. Its command exits zero only when
this expected pattern is actually observed. Saved failures replay with exit code 1.

Validation: **55 tests and 120 repeated subtests passed locally** with actual
SQLite, Qdrant, Chroma, pgvector and LangChain APIs. Wheel and source distribution
passed `twine check`; an installed wheel was exercised outside the source checkout.

Known release blockers: GitHub-hosted CI was attempted but the account's billing
lock prevented all jobs from starting. This is a locally tested prerelease, not a
claim of green hosted CI. PyPI publishing needs owner-side trusted-publisher setup.
No independent user feedback or production application validation is claimed.

Use disposable test services and synthetic documents only. Passing finite checks
does not prove physical erasure, indefinite absence or arbitrary distributed safety.
See README.md and docs/roadmap.md for precise scope and current outcome status.
