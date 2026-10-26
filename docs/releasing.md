# Release procedure

Candidate version: 0.2.0rc1. Repository:
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

The owner is currently creating or signing into a PyPI account. No PyPI upload
is claimed until the account-side publisher registration and upload succeed.

Name checks are point-in-time observations, not reservations or trademark
clearance. `dependency-inventory.json` records installed validation-environment
license metadata, including optional libraries and developer tools. Dependencies
are not vendored; this inventory is not a legal compatibility certification.

Independent feedback must come from real users, following `feedback-study.md`.
A prepared launch post in `launch.md` has not been submitted to external forums.
