# Application and storage adapters

The built-in store adapters allocate a fresh random namespace per case. They must
upsert a `Document`, delete by tenant/id, return all persisted records in `scan`,
query through the backend's actual retrieval API, and clean up only their own
namespace. See `recallfsck.stores.Store`. Do not build observed results from the
reference model or filter away unexpected records before evaluation.

An application factory is explicitly loaded with `--app installed_module:factory`.
The factory receives `(store, worker)` and returns an object with:

| Method | Contract |
| --- | --- |
| `async put(document)` | Acknowledge actual application ingestion/upsert |
| `async delete(tenant, doc_id)` | Acknowledge actual logical source deletion |
| `async migrate()` | Change all live synthetic documents to v2 embeddings |
| `async index(tenant, doc_id, paused, resume)` | Capture source, signal paused before final write, wait on resume, finish actual worker |
| `retrieve(tenant, model)` | Actual application retrieval; return complete document dictionaries |
| `close()` | Optional synchronous cleanup of owned application resources |

Document dictionaries have id, tenant, text, revision and model. Synthetic
embeddings are `[1,0]` for v1 and `[0,1]` for v2. The independent reference model
tracks expected live records; the adapter must never receive that model.

Use `examples/adapter_template.py` as the scaffold. The executable
`examples/http_application.py` wraps the tiny service behind HTTP and serves as a
working integration example, including real scheduling hooks and cleanup.
Applications without reliable pause/resume hooks cannot support these controlled
race checks honestly; implement hooks in staging or use the non-race subset.

The corrected fixture's lock is in-process. A distributed implementation needs
its own fencing/version checks and atomic commit semantics. Substituting that
fixture for a real application does not validate the real application.

Qdrant uses acknowledged REST writes, filtered vector queries and paginated
scrolls. Chroma uses an ephemeral local client, explicit vectors and filtered
queries; no model download is needed. pgvector uses psycopg, parameterized queries,
quoted table identifiers and cosine distance. Install `vector` on the disposable
server before running; the adapter never installs extensions itself.

Official references: [Qdrant API](https://api.qdrant.tech/api-reference),
[Chroma Python client](https://docs.trychroma.com/reference/python),
[pgvector](https://github.com/pgvector/pgvector), and
[Hypothesis](https://hypothesis.readthedocs.io/en/latest/).
