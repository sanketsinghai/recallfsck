# Original 90-day roadmap: delivery status

This implements the engineering scope as a local release candidate. A roadmap's
adoption and public-launch milestones require evidence from outside this workspace.
They are not replaced with synthetic claims.

| Original stage | Delivered | External milestone still pending |
| --- | --- | --- |
| Days 1–7: technical proof | Buggy/correct workers, deterministic create/delete/index races, real Qdrant evidence | None for the bounded synthetic experiment |
| Days 8–14: testing core | Independent document model, operation histories, assertions, schema-versioned JSON replay | None for the implemented API |
| Days 15–30: first release | Qdrant/Chroma adapters, pytest fixture, JSON/HTML/JUnit, installation and docs | Unfamiliar developer installation feedback |
| Days 31–60: reliability | Hypothesis search/shrinking, replay minimizer, pgvector, deadlines/monitoring, isolation and GitHub Actions | CI execution on an actual hosted repository |
| Days 61–90: release preparation | Local HTTP demonstration, application adapter template, migration checks, release candidate metadata, changelog, build workflow and community files | Public release destination, independent feedback and real external application integration |

The suite tests all seven proposed invariant families. Model migration uses
same-dimensional synthetic embeddings; real providers and dimension-changing
rebuilds are not claimed. Application integration is an explicit adapter contract;
a universal no-hook integration across arbitrary frameworks remains unrealistic.

The first five proposed implementation issues are represented in this code:
reference state (`suite.py`), Qdrant adapter (`stores.py`), scenario runner
(`suite.py`), scheduler (asyncio pause/resume events), and CI evidence
(`reporting.py`, workflows). No GitHub issues were filed because no remote
repository has been configured.

## Launch checklist requiring the owner or independent contributors

- Select/create a hosted repository and verify name/package/trademark availability.
- Set up private security and conduct contacts and dependency-license review.
- Run the committed workflows in GitHub and review uploaded evidence.
- Have several unfamiliar developers run the docs and reproduce failures.
- Integrate one real application through its actual ingestion/retrieval APIs.
- Review the candidate, configure publishing and authorize the public release.
- Gather feedback from relevant maintainers; do not claim discovered upstream bugs
  or publish promotional messages without an actual reproducible finding.

A local prototype can establish repeatable observations. It cannot establish
adoption, unique prior art, production correctness or market demand.
