# 90-day outcome status

Repository: https://github.com/sanketsinghai/recallfsck

The engineering scope is implemented and locally tested. Public infrastructure
and adoption outcomes have separate evidence and blockers; they are not counted
as complete simply because implementation exists.

| Outcome | Status and evidence |
| --- | --- |
| Deterministic red/green proof | Complete: buggy/correct fixtures, three controlled races |
| Reference model and replay | Complete: full records, operation history, schema-2 reproductions |
| Qdrant, Chroma and pgvector | Complete: real integrations and cleanup tested |
| Lifecycle invariants | Complete for the documented synthetic scope: ten scenarios |
| Failure discovery and shrinking | Complete: Hypothesis search plus deletion-based minimization |
| Consistency windows and isolation | Complete: convergence, bounded monitoring and filtered retrieval checks |
| pytest, reports and demo | Complete: pytest fixture, JSON/HTML/JUnit and real HTTP boundary |
| Real ecosystem integration | Complete: twenty cases using actual LangChain/Chroma ingestion, deletion, embedding and retrieval APIs |
| Repository and original five issues | Complete: public source; implementation issues #1–#5 created and closed |
| Private security reporting | Complete: GitHub private vulnerability reporting enabled |
| Release distributions | Complete: wheel/sdist built, checked, independently installed and exercised |
| Hosted CI execution | Complete: Python 3.11/3.12/3.13 and real database jobs passed on main |
| PyPI publishing | Complete: 0.2.0rc2 published through trusted publishing; clean PyPI installation, demo, replay and HTTP checks passed |
| Independent developer feedback | Pending: no participants have provided results yet |
| External user's production/staging application | Pending: LangChain API coverage is not independent validation of an existing user's application |

Successful hosted CI:
https://github.com/sanketsinghai/recallfsck/actions/runs/40374759837

Successful publication:
https://github.com/sanketsinghai/recallfsck/actions/runs/40375794561

Published package:
https://pypi.org/project/recallfsck/0.2.0rc2/
Distribution hashes were verified against public PyPI metadata; see
`pypi-publication.json` for the receipt.

The earlier billing lock is resolved. PR #9 fixed the installed HTTP demo command.
The full database job passed **55 tests and 120 repeated subtests**, including
real databases and LangChain integration. The Python matrix passed with optional
database tests covered separately in the dedicated database job.

See `releasing.md` for exact PyPI registration values, `feedback-study.md` for the
independent-user protocol, `implementation-issues.json` for completed issues,
and `launch.md` for the prepared launch draft. No external outreach was sent.

Model migration changes known same-dimensional synthetic vectors. Tests do not
establish semantic answer quality, physical erasure, distributed linearizability,
untested query paths, real dimension-changing rebuilds or indefinite absence.
The PyPI name returned HTTP 404 on October 26, 2026; that is not name reservation,
trademark clearance or unique-prior-art proof.
