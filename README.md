# RecallFSCK

A delete returns success. An older ingestion worker finishes afterward and puts
that document back into search. RecallFSCK runs that schedule, compares actual
retrieval with an independent reference model, and saves a replayable failure.

## One-command demo

Install the published release candidate with Python 3.11+:

```sh
python -m pip install 'recallfsck==0.2.0rc2'
recallfsck demo
```

[PyPI release](https://pypi.org/project/recallfsck/0.2.0rc2/) ·
[Publishing checks](https://github.com/sanketsinghai/recallfsck/actions/runs/40375794561)

The demo runs ten scenarios against two applications. The deliberately buggy
worker fails three races: delete/index, replacement/index, and migration/index.
The corrected worker passes all ten. Demo exits 0 only when that exact pattern is
observed. The evidence still labels the buggy cases FAIL.

Open `report/index.html`; each case also has JSON evidence. `report/junit.xml`
records failures for CI. These are executed results, not illustrative screenshots.

```sh
recallfsck init --adapter sqlite
recallfsck test --config recallfsck.yaml
recallfsck replay report/buggy-delete-during-index.json
recallfsck minimize report/buggy-delete-during-index.json --output report/minimal
recallfsck explore --worker buggy --examples 100 --output report/discovery
```

Replay, minimize and explore exit 1 when they reproduce an integrity failure.
Exit 2 means an input, service, dependency or execution error. A missing database
never becomes PASS. `explore` uses Hypothesis to search actual executions and
shrink failures; `minimize` produces a 1-minimal valid deletion subsequence.

## What is checked

| Invariant | Observed evidence |
| --- | --- |
| Create | Acknowledged source appears in application queries and index scan |
| Replacement | Only the expected revision/content remains |
| Metadata | Stored and retrieved revision matches expected metadata |
| Delete | Document remains absent throughout the configured monitor window |
| Idempotency | Repeat upsert/delete does not introduce duplicate records |
| Isolation | Alpha, beta, and outsider queries expose only authorized records |
| Concurrency | Paused stale workers cannot overwrite deletion, revision or model |
| Model migration | All live records move to the synthetic v2 vector configuration and remain retrievable |

The generation check and final commit share the deletion lock in the corrected
fixture. The scheduler coordinates with events rather than hoping sleeps cause a
race. Passing results cover finite observation windows, not indefinite absence.

## Integrations

| Adapter | Installation | Runtime |
| --- | --- | --- |
| SQLite | Base package | Disposable in-memory SQL; no vector-search claim |
| Qdrant | Base package | Disposable Qdrant REST collection |
| Chroma | `pip install -e '.[chroma]'` | Embedded ephemeral Chroma vector collection |
| pgvector | `pip install -e '.[pgvector]'` | Disposable table on a PostgreSQL server with vector enabled |

```sh
# Start isolated databases (Docker Compose):
docker compose up -d --wait
recallfsck demo --backend qdrant --url http://127.0.0.1:16333 --output report/qdrant
recallfsck demo --backend chroma --output report/chroma
RECALLFSCK_URL=postgresql://postgres:recallfsck-local-only@127.0.0.1:15432/recallfsck \
  recallfsck demo --backend pgvector --output report/pgvector
docker compose down -v
```

For source integration, implement the [application adapter contract](docs/adapters.md).
A runnable [HTTP application example](examples/http_application.py) goes through
real local HTTP calls while using the runner's disposable index:

```sh
recallfsck demo --app recallfsck.demo_http:create_application --output report/http
```

A real LangChain/Chroma integration is available below. Dify and other applications
need their own adapters. Backend conformance and bundled fixtures do not prove an
unrelated production application's correctness.

## pytest

```python
def test_delete_integrity(recallfsck_runner):
    result = recallfsck_runner("delete-during-index", worker="fixed")
    assert result["status"] == "PASS", result["first_divergence"]
```

Install the `test` extra for pytest and Hypothesis. Importing the plugin does not
create a database or automatically add tests to your project.

## Development and release

```sh
python -m pip install -e '.[all,test]'
python -m pytest -q
ruff check .
python -m build
python -m twine check dist/*
```

See [usage](docs/usage.md), [architecture](docs/architecture.md),
[roadmap status](docs/roadmap.md), [validation](VALIDATION.md), and
[release instructions](docs/releasing.md).

## Limits and safety

Run mutating tests only on disposable services and synthetic data. Each adapter
creates and cleans up its own randomly named collection/table. Interrupted runs
may leave owned objects behind; existing namespaces cannot be selected.

The vector tests use known two-dimensional synthetic embeddings. Migration checks
cover same-dimensional configuration changes, not a real model's semantic quality
or cross-dimension rebuild. Queries are top-100 with full index scans as a separate
check; generated schedules are capped at 200 operations and the bundled corpus
fits below the query limit. Unknown applications need explicit integration and
scheduling hooks. Network calls have adapter timeouts; consistency settings are
not a hard wall-clock cancellation limit for blocking drivers.

Logical source deletion, retrieval absence, and physical erasure are distinct.
This tool does not prove disk/backup erasure, untested query paths, distributed
linearizability, production authorization policy or arbitrary future absence.
There is no production scanning mode. Saved reports contain test document text;
use synthetic inputs. No hosted service or API keys are required for the demos.

Repository: https://github.com/sanketsinghai/recallfsck . The PyPI name returned
HTTP 404 when checked on October 26, 2026; this does not reserve the name or
establish trademark clearance.
MIT license; optional dependencies keep their respective licenses.

## Real LangChain integration

```sh
python -m pip install -e '.[langchain,test]'
recallfsck demo --backend chroma \
  --app recallfsck.integrations.langchain_chroma:create_application \
  --output report/langchain
```

In this integration, writes, deletion, embedding and retrieval call the actual
LangChain Chroma vector-store APIs. The controlled ingestion scheduling and the
injected bugs belong to RecallFSCK's demonstration application. No upstream
LangChain defect or production application correctness is claimed.
