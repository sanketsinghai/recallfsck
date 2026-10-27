# Usage

Install the repository with `python -m pip install -e '.[all,test]'`. Activate its
virtual environment first. Python 3.11 or newer is required.

`recallfsck init --adapter qdrant` writes `recallfsck.yaml` exclusively; it refuses
to overwrite an existing config. The generated file enumerates the supported
scenarios. `recallfsck test --config recallfsck.yaml` runs them with the corrected
fixture by default. Choose `--app module:factory` to run your integration.
Config files never import application code; that requires an explicit CLI flag.

```yaml
backend: sqlite
worker: fixed
consistency_seconds: 0.1
monitor_seconds: 0.02
poll_seconds: 0.01
output: report
scenarios:
  - create
  - update
  - metadata
  - delete
  - idempotency
  - isolation
  - delete-during-index
  - update-during-index
  - migration
  - migration-during-index
```

`url` is optional for remote databases. Prefer `RECALLFSCK_URL` for a DSN with
credentials. Precedence: CLI, environment URL, explicit config, defaults.
Unknown config keys, unsupported scenarios and invalid timings produce errors.
Timings must be finite and between 0 and 60 seconds; poll interval must be positive.

Use `--scenario delete --scenario isolation` to select checks. `--worker` can
select fixed, buggy, stale-update, stale-metadata, tenant-leak, migration-loss or
duplicate. These are deliberately injected fixture defects, not faults in Qdrant,
Chroma or PostgreSQL. `demo` always compares buggy and fixed fixtures.

Each observation queries every combination of alpha/beta/outsider and v1/v2,
plus a separate full index scan. It compares complete records, including text,
revision, tenant and model. During convergence, mismatches may settle within the
consistency deadline. Once convergence occurs, any later mismatch during the
monitor window fails. At least one read occurs even with zero deadlines.
Observation timestamps and sample matches are stored in the artifact.

`replay CASE.json` uses the saved worker, schedule and timing settings against a
fresh store. Choose the saved `--backend` explicitly for non-SQLite artifacts.
Use the original `--app` when the artifact came from an application adapter.
Endpoints and credentials are not persisted. Schema 1 replay delegates to the
original prototype; schema 2 is the current format.

`minimize CASE.json` reexecutes candidate subsequences against fresh stores and
retains failures on the same divergence path/tenant/model. It produces a
1-minimal valid subsequence, not a globally minimal proof or a byte-for-byte
identical causal failure. Review the resulting evidence.

`explore --worker buggy --examples 100` uses Hypothesis generation/shrinking to
find a failing sequence. Blocks include writes, deletes, metadata, migrations
and balanced controlled races. A budget with no failure is not a safety proof.
Hypothesis may perform extra executions during shrinking beyond `--examples`.

Each run writes summary JSON, per-case JSON, HTML and JUnit. Use a different
`--output` per run to preserve evidence. The summary and JUnit describe only the
current run; older per-case files can remain in a reused directory. Case ERROR
records deliberately omit driver messages that might expose connection secrets.
For debugging, check service health and call your adapter directly with synthetic
inputs; error type is retained in the report.

Exit codes: 0 all expected checks pass (or demo matches its expected pattern),
1 observed integrity violation, 2 configuration or execution error. In a demo,
JUnit retains expected buggy failures even though the demo command returns 0.
Use `test --worker fixed` as a CI regression gate.

## Report format and execution diagnostics

`report.json` adds a versioned run envelope; `summary.json` remains a case list for
existing consumers. See [the report contract](report-format.md). The actual
application identifier is separate from the fixture worker in HTML and JUnit.

Durations are measured complete-case execution times. Legacy artifacts without
a measurement say "Not recorded" rather than implying a zero-duration run.
Standard reports also distinguish execution ERROR from integrity FAIL, and a demo
whose expected failures match does not relabel those failures as passes.

Execution errors now include safe hints for unreachable services, backend HTTP
status, missing optional adapters and invalid input. Endpoint URLs, driver error
text and credentials are not copied into these hints. Input validation failures
produce a standard ERROR report when the chosen output directory is writable.
