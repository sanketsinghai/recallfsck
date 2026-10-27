# Review corrections — 0.2.0rc3

The review identified a real HTML reporting bug and stale published description.
This correction release addresses them and strengthens verification of the actual
wheel. It does not certify production safety or independent adoption.

## Findings and evidence

| Review item | Action and actual result |
| --- | --- |
| Application/Worker HTML mismatch | Fixed with separate columns; parsed-table regression fails on published 0.2.0rc2 and passes with the corrected writer |
| Outdated PyPI description | Removed the obsolete name-availability note; the next distribution README uses the published install command |
| Seven adapter scenarios | Reconstructed from the supplied categories and executed against the actual installed 0.2.0rc2 package: 2 PASS and 5 detected FAIL, seven expectations met |
| Original reviewer QA scripts | Not supplied: the pasted attachment described an archive but contained no archive, scripts or download URL; no claim that those original files were executed |
| Standard reports | Responsive offline HTML, run UUID/version/time/counts, distinct identities, measured durations, expandable observed evidence, JSON envelope and JUnit metadata |
| Exact-wheel compatibility | CI installs built wheels outside the checkout on Python 3.11–3.13; the publishing workflow additionally verifies the identical upload artifact on all three versions before upload |
| Independently maintained application | Unmodified Open WebUI v0.12.4 was exercised through actual ingestion, replacement, retrieval and deletion APIs, with its own pgvector index inspected separately: four bounded checks passed |
| Independent user adoption / real upstream fault | Not established: this was an author-run trial; no participant report or upstream fault was invented |
| Stable 0.2.0 | Not promoted; retain release-candidate status until the documented readiness criteria are met |

## Executed QA controls

`qa/test_recallfsck_external.py` implements its own application controls and calls
the installed package runner and report writer. It does not copy the comparator
or import RecallFSCK's built-in application fixture.

| Case | Expected and observed integrity verdict |
| --- | --- |
| Correct create | PASS |
| Correct delete during indexing | PASS |
| Deleted-document resurrection | FAIL, detected |
| Stale replacement revision | FAIL, detected |
| Cross-tenant leakage | FAIL, detected |
| Migration loses records | FAIL, detected |
| Duplicate repeated upsert | FAIL, detected |

The QA process succeeds when those seven expectations match. Its JUnit/HTML still
contain five actual integrity failures. This is intentionally not described as
seven passing application verdicts.

## Open WebUI trial scope

Pinned image:
`ghcr.io/open-webui/open-webui:v0.12.4-slim@sha256:41812075aede8ada8497cb2b71c76412978633eee72775bb77796f593d03b677`

Upstream revision: `33c1978d5bad52a31df75ea55143025dfad18d16`.
Observed receipt: `qa/openwebui-observed.json`.

The first attempted configuration used Chroma, which the slim image rejects with
HTTP 503. That was an execution/configuration problem, not an integrity pass or
an attributed application bug. The corrected setup used the supported pgvector
backend and a local deterministic 64-dimensional embedding provider. No upstream
application source changes were made.

Four actual checks passed: create/retrieve, replacement without stale revision,
repeated indexing without duplicates, and deletion with index-record absence.
After deletion the file API returned HTTP 404. Query denial was not treated as
proof of index absence: the application's own index was inspected separately.

Not tested: tenant isolation (authentication disabled only in the disposable
instance), controlled races (no pause/resume hook installed), model migration,
real embedding semantics, LLM answer quality and long-term deletion absence.
A passing bounded lifecycle trial does not prove these untested properties.

See `qa/README.md` for commands and `docs/report-format.md` for output contracts.
Issue #8 remains open for genuine independent developer and application-team
reports. No external outreach was sent as part of this correction work.
