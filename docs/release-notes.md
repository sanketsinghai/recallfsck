# RecallFSCK 0.2.0rc3

Correction release for application identity, standard reporting and package QA.

- Fix the HTML Application column to show the actual adapter, with a separate Worker column.
- Standardize current and legacy HTML, versioned JSON run manifests and JUnit evidence.
- Add counts, UUID run IDs, generation timestamps, package versions, measured case durations, scope and expandable evidence/reproduction details.
- Keep real FAIL/ERROR verdicts separate from expected demo/QA outcomes.
- Add safe actionable diagnostics without persisting driver credentials.
- Remove the obsolete availability note from the package description.
- Add reconstructed seven-case adapter QA: two valid PASS verdicts and five detected faults, with clear provenance.
- Verify exact upload wheels on Python 3.11, 3.12 and 3.13 before publication.
- Include a reproducible author-run trial against unmodified Open WebUI v0.12.4: four bounded lifecycle checks passed using actual APIs and its own pgvector index.

After publication:

```sh
python -m pip install 'recallfsck==0.2.0rc3'
recallfsck demo
```

Open `report/index.html` for the standard report. Demo intentionally retains three
buggy-worker failures; all corrected-worker cases should pass.

The original review's downloadable QA archive was not attached. Our seven-case
reconstruction is labeled accordingly and is not represented as the reviewer's
original test scripts or independent participant validation.

This remains a release candidate. The Open WebUI trial does not cover tenant
isolation, controlled races, model migration, real embedding semantics or LLM
answers. No upstream bug or independent adoption is claimed. Scope and receipts
are documented in `docs/review-corrections.md` and `qa/openwebui-observed.json`.
