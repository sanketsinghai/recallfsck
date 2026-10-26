# RecallFSCK 0.2.0rc2

Stateful lifecycle integrity checks for RAG indexes, with replayable evidence.

This candidate includes the installed HTTP demo correction and the first PyPI
publication workflow after successful hosted CI.

Implemented:
- Ten lifecycle scenarios covering create, update, metadata, delete, idempotency,
  isolation, controlled indexing races and synthetic model migration.
- Real Qdrant, Chroma, pgvector and LangChain/Chroma API integrations.
- Independent reference state, controlled scheduling and finite consistency windows.
- Hypothesis discovery/shrinking, replay, minimization and pytest integration.
- JSON/HTML/JUnit evidence and a runnable HTTP application.

Install the published prerelease:

```sh
python -m pip install 'recallfsck==0.2.0rc2'
recallfsck demo
```

The demo intentionally produces three buggy-worker failures and ten corrected-worker
passes. Seven other buggy-worker checks pass. Demo exits zero only when the
expected pattern is observed. Failure replay returns exit code 1.

Validation: Python 3.11, 3.12 and 3.13 passed hosted CI. The full real-database suite
passed **55 tests and 120 repeated subtests**, including LangChain integration.
See https://github.com/sanketsinghai/recallfsck/actions/runs/40374759837 .

Trusted PyPI publication succeeded:
https://github.com/sanketsinghai/recallfsck/actions/runs/40375794561 .
The published wheel was installed from public PyPI in a fresh environment outside
the checkout. Demo, saved failure replay, HTTP demo and dependency checks passed.
Attached GitHub distribution files match the hashes published by PyPI.

Only disposable services and synthetic documents are supported. Passing finite
checks does not prove physical erasure, indefinite absence, arbitrary distributed
safety or production application correctness. No independent user feedback is
claimed. See README.md and docs/roadmap.md for scope and remaining adoption work.
