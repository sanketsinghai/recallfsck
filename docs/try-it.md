# First run: inspect and replay a real test failure

You need Python 3.11+ and a shell. The first run uses a disposable in-memory
SQLite index, so no Docker, hosted account, model download or API key is needed.

## Install the published candidate

In a fresh folder, on macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'recallfsck==0.2.0rc2'
recallfsck demo
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install 'recallfsck==0.2.0rc2'
recallfsck demo
```

If shell activation is unavailable, run commands with the environment's Python
and `python -m recallfsck demo`. To include prereleases without an exact version,
use `python -m pip install --pre recallfsck`; see
[pip's prerelease rules](https://pip.pypa.io/en/stable/cli/pip_install/#pre-release-versions).
These instructions do not assume stable 0.2.0 has been released.

## Recognize the expected outcome

Twenty cases run: ten with a deliberately buggy application and ten with a
corrected application. Three buggy races should show FAIL: delete-during-index,
update-during-index and migration-during-index. All ten corrected cases should
show PASS. The other seven buggy cases should also pass.

The final message should say the demo matched expected red/green outcomes, and
the command exits zero. The failures demonstrate defects deliberately included in
our application; they are not bugs attributed to SQLite or another framework.

## Inspect the evidence

Open `report/index.html` in your browser. Look at the buggy delete-during-index
case, or open `report/buggy-delete-during-index.json` in an editor.

The history should show insertion, a paused indexing job, deletion, the resumed
old job and observation. The reference expects no document; the index scan and
application retrieval expose the restored record. Compare that evidence with
`report/fixed-delete-during-index.json`.

## Reproduce it on a fresh index

```sh
recallfsck replay report/buggy-delete-during-index.json --output report/replayed
```

This should report FAIL and exit **1**. That means reproduction succeeded; it
is not an installation error. Execution/configuration errors use exit code 2.
For an all-passing suite instead, run:

```sh
recallfsck test --worker fixed --output report/fixed
```

## Tell us what actually happened

Use the [installation feedback form](https://github.com/sanketsinghai/recallfsck/issues/new?template=feedback.yml).
Record Python/OS, installed version, commands, actual outcomes, setup time and
anything that needed help. Share synthetic evidence only. Unexpected results are
useful; you do not need to fix them before reporting.

This demonstrates the checker against our supplied application, not your own
RAG system. If you maintain a separate application, follow the
[application adapter contract](adapters.md) and
[independent validation protocol](feedback-study.md). A successful library demo
does not prove your application's ingestion and retrieval behave correctly.
