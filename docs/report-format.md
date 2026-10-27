# Standard report outputs

Current and legacy CLI runs use one report writer. HTML is a portable, responsive
single file with no external stylesheets, scripts or network dependencies.

| File | Contract |
| --- | --- |
| `index.html` | Run status, counts, UTC generation time, package version, actual application and worker in separate columns, duration, evidence and eligible replay commands |
| `report.json` | Run envelope schema 1: UUID run ID, generation time, package version, status, counts, known durations, timing coverage, safe command context, scope and case records |
| `summary.json` | Backward-compatible list of case records; existing consumers need not switch to the run envelope |
| `WORKER-SCENARIO.json` | Per-case reproduction/evidence record; execution artifact schemas remain separate from report schema |
| `junit.xml` | Conventional testsuite/testcase XML: counts, measured times, application/backend/worker properties, failure/error evidence |

`PASS`, `FAIL` and `ERROR` mean actual integrity results. A demo with the expected
three deliberately buggy failures may exit zero while its HTML, JSON and JUnit
still contain those failures. The report explicitly separates a successful QA
expectation from an integrity pass. An empty run is `NOT RUN`, not `PASS`.

Durations measure complete CLI case execution, including setup and cleanup.
Legacy records without timing are labeled "Not recorded"; no measurement is
invented. A run total is present only if all case durations are known. Generation
time is not presented as an execution start time.

HTML escapes observed text. XML sanitizes characters disallowed by XML 1.0.
Invalid status, malformed case names and duplicate case identities are rejected
before report writing. No endpoint, DSN, raw command line or driver exception text
is copied into the run context. Safe error hints explain service availability,
HTTP status and optional dependencies without exposing credentials.

Programmatic adapters outside the CLI need to include the actual `application`
identifier. Old records without it are labeled `fixture`; this fallback never
uses `fixed` or `buggy` as the application name. External-application trials with
no replayable core schedule do not advertise a generic CLI replay command.

These files are evidence for the executed paths and finite observation windows.
A conventional JUnit representation or polished HTML layout does not certify
production safety, physical erasure or independent adoption.
