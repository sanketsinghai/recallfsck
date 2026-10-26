# Release procedure

Candidate version: 0.2.0rc2. Repository:
https://github.com/sanketsinghai/recallfsck

1. Run hosted CI and review actual adapter evidence.
2. Build with `python -m build` and validate with `python -m twine check dist/*`.
3. Verify the wheel in a fresh environment outside the checkout.
4. Tag the tested commit and attach distributions to a GitHub prerelease.
5. For PyPI, the owner must register a pending trusted publisher at
   https://pypi.org/manage/account/publishing/ with project `recallfsck`, owner
   `sanketsinghai`, repository `recallfsck`, workflow `publish.yml`, environment
   `pypi`. For TestPyPI use its own account and environment `testpypi`.
6. Dispatch `Publish Python package` on the matching version tag and choose the
   configured index. The workflow reruns CI, checks tag/version agreement, builds
   distributions and uses OIDC trusted publishing. Passwords and API tokens are
   not stored in the repository or requested in chat.

Version 0.2.0rc2 is published at https://pypi.org/project/recallfsck/0.2.0rc2/ .
The workflow completed successfully and a clean public-PyPI installation passed
the demo, failure replay, HTTP demo and dependency check. Distribution hashes
match the workflow artifacts. See `pypi-publication.json` for the receipt.

Name checks are point-in-time observations, not reservations or trademark
clearance. `dependency-inventory.json` records installed validation-environment
license metadata, including optional libraries and developer tools. Dependencies
are not vendored; this inventory is not a legal compatibility certification.

Independent feedback must come from real users, following `feedback-study.md`.
A prepared launch post in `launch.md` has not been submitted to external forums.

## Stable 0.2.0 readiness

Keep 0.2.0rc2 available for trials while collecting adoption evidence. Release
0.2.0 after reviewing these criteria; a version rename alone does not supply it:

- Several developers unfamiliar with the implementation can install, run and
  explain the demo and replay using the published instructions. Record their
  actual reports and fix onboarding problems they encounter.
- At least one independently maintained RAG application is exercised through its
  actual ingestion/deletion/retrieval paths. Record its repository/version,
  adapter changes, hooks, scope and replayable evidence. Our supplied fixtures
  and LangChain bridge do not satisfy this criterion by themselves.
- Triage the resulting correctness and compatibility findings; resolve known
  release-blocking defects or explicitly narrow unsupported scope.
- Confirm the supported adapter contract, artifact compatibility and limitations
  in the stable documentation. Include the corrected README in the distribution
  so the obsolete HTTP 404 note disappears from the PyPI description.
- Pass the Python matrix, real database jobs, package checks and clean public
  installation checks for the final release commit.

Then prepare version `0.2.0` on a branch, review its changelog, merge after CI,
tag `v0.2.0`, and use the existing trusted-publishing workflow. Verify
`python -m pip install recallfsck` in a fresh environment, with no prerelease
flag or pin, and confirm the installed version is 0.2.0. Mark its GitHub release
as stable. These are future release steps, not actions already completed.

The existing 0.2.0rc2 package is immutable. Editing the repository README prepares
the correction for the next package upload; it does not change that version's
already published description.
