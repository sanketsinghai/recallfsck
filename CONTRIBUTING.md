# Contributing

Use Python 3.11+ in a virtual environment. Install with
`python -m pip install -e '.[all,test]'`, then run `ruff check .` and
`python -m pytest -q`. Start the disposable services with
`docker compose up -d --wait` for integration coverage:

```sh
RECALLFSCK_QDRANT_URL=http://127.0.0.1:16333 \
RECALLFSCK_PGVECTOR_URL=postgresql://postgres:recallfsck-local-only@127.0.0.1:15432/recallfsck \
  python -m pytest -q
```

Run affected adapter demos and include replayable synthetic failure evidence.
Keep changes scoped, preserve old artifact replay, and document the exact scope
of every invariant. Add a deliberately faulty fixture when adding an invariant;
checking only a passing implementation cannot show the checker detects a defect.
Do not expose private documents, tokens or connection credentials in reports.

See CODE_OF_CONDUCT.md, SECURITY.md and docs/adapters.md before contributing.
