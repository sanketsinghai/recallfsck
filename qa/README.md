# Review coverage against the installed wheel

The pasted review mentioned an archive but supplied no archive or source scripts.
These scripts reconstruct the described coverage; they are not presented as the
reviewer's original files or as independent user/application evidence.

From a clean environment with RecallFSCK installed, run these scripts by path:

```sh
python /path/to/checkout/qa/test_recallfsck_external.py --output report/seven-case-qa
python /path/to/checkout/qa/test_recallfsck_reporting.py
```

The first script calls the actual installed `run_sequence`, store and report
writer. Its application implementation does not import the product's fixture or
copy its comparison function. Expected integrity verdicts are **2 PASS and 5
FAIL**, while all seven QA expectations must match. The process exits zero only
when those expectations hold. JUnit retains five real integrity failures.

The second script parses the actual HTML table and checks the distinct
Application/Worker columns. It fails against the original 0.2.0rc2 report writer.

The exact built wheel is also installed and exercised on Python 3.11, 3.12 and
3.13 in CI. External user validation remains separate in issue #8.

## Actual Open WebUI application trial

The pinned slim Open WebUI v0.12.4 image requires pgvector. The Compose recipe
provides its own isolated PostgreSQL and synthetic embedding sidecar. Only the
application HTTP port is bound to localhost; no real account or API key is used.

```sh
docker compose -f qa/openwebui-compose.yaml up -d --wait
python qa/openwebui_smoke.py \
  --container "$(docker compose -f qa/openwebui-compose.yaml ps -q openwebui)" \
  --output report/openwebui
docker compose -f qa/openwebui-compose.yaml down -v
```

Run this only with that fresh disposable instance. It authenticates its synthetic
local account, uploads JSON text as a file, queries actual application retrieval,
replaces its content, repeats indexing and deletes it. The application's own
pgvector index is inspected separately via a read-only container command; denied
HTTP retrieval after deletion is not interpreted as proof of index absence.

The trial uses unmodified upstream application code and a deterministic local
64-dimensional embedding provider. It does not exercise controlled races, tenant
isolation, embedding migration, semantic embedding quality or LLM answers.
This is author-run evidence against an independently maintained application,
not independent user feedback. No upstream fault was discovered in these checks.
