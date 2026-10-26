# Release-candidate validation — October 26, 2026

Executed locally on Python 3.11.15. Candidate: **0.2.0rc1**.

## Automated checks

Full suite with real database endpoints: **55 tests passed and 120 repeated
subtests passed, no skips**. Evidence: `report/release-tests.xml`.

This includes:

- All ten lifecycle scenarios against real SQLite, Qdrant v1.13.4, Chroma 1.5.9
  and PostgreSQL 16 with pgvector.
- Fixed-worker passes and deliberately buggy-worker race failures.
- Independent negative controls for stale content, metadata, duplicate records,
  tenant leakage and migration loss.
- Real vector corruption during migration: metadata remained correct but all
  three vector backends failed the retrieval assertion as intended.
- Actual collection/table cleanup on Qdrant, Chroma and pgvector.
- Hypothesis-generated operation sequences and automatic search/shrinking.
- Saved evidence replay and deletion-based minimization with fresh stores.
- Convergence retries, deadline expiry and resurrection during monitoring.
- Malformed inputs, invalid timings/schedules, backend unavailability, failed
  scheduling hooks, premature hook completion and HTML escaping.
- pytest fixture integration, the real HTTP transport demo, and twenty
  lifecycle cases using langchain-chroma 1.1.0 and langchain-core 1.7.0.

## Executed product demos

Each backend demo ran twenty cases: ten with the buggy fixture and ten with the
corrected fixture. Three buggy races failed; all other cases passed. Each demo
returned 0 because the exact expected red/green pattern was observed.

| Runtime | Local evidence |
| --- | --- |
| SQLite | `report/release-sqlite/index.html` |
| Qdrant | `report/release-qdrant/index.html` |
| Chroma | `report/release-chroma/index.html` |
| pgvector | `report/release-pgvector/index.html` |
| Actual HTTP application boundary | `report/release-http/index.html` |
| All corrected scenarios from generated YAML | `report/release-fixed/index.html` |
| Hypothesis-discovered failure | `report/release-discovery/index.html` |
| Minimized failure | `report/release-minimized/index.html` |
| Fresh-collection Qdrant replay | `report/release-qdrant-replay/index.html` |

The replay, discovery and minimization commands returned 1, correctly signaling
an observed integrity violation. Backend outages return 2 and JUnit ERROR, not PASS.
The committed `examples/resurrection.json` is actual SQLite demo evidence.

## Packaging and code checks

- Ruff checks and format checks passed.
- `pip check` found no broken requirements.
- Source distribution and universal Python wheel built successfully.
- `twine check` passed for both distribution files.
- Built wheel installed in a clean temporary virtual environment.
- Installed SQLite and packaged HTTP demos ran from outside the source checkout.
- Docker Compose startup and disposable pgvector extension initialization checked.

## Limits

Python 3.12/3.13 checks and hosted GitHub workflows are configured, not executed
locally. The LangChain integration exercises actual ecosystem APIs using our synthetic
application. Independent user feedback, PyPI publication, trademark clearance,
physical erasure and production safety are not established. Synthetic model migration changes known same-dimensional vectors;
it does not validate real embedding quality or dimension-changing rebuilds.
See `docs/roadmap.md` for outstanding external release milestones.

## Public repository and hosted CI attempt

Source is published at https://github.com/sanketsinghai/recallfsck .
Hosted CI was attempted at
https://github.com/sanketsinghai/recallfsck/actions/runs/40370585154 .
No job started. GitHub reported: “The job was not started because your account is
locked due to a billing issue.” This is an account-side blocker, not a passed or
executed hosted suite. Local integration tests, including LangChain/Chroma,
passed 55 tests and 120 repeated subtests.

## Hosted CI recovered and passed

The billing lock is resolved and the installed HTTP demo command was fixed in
PR #9. Main passed the Python 3.11/3.12/3.13 matrix and actual database jobs:
https://github.com/sanketsinghai/recallfsck/actions/runs/40374759837 .
The full database suite passed 55 tests and 120 repeated subtests.
Version 0.2.0rc2 includes that workflow correction; product runtime behavior is
unchanged from the locally and subsequently remotely verified candidate.
