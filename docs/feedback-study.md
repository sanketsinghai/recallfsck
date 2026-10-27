# Independent developer validation

This protocol is ready for volunteers. No independent participant results have
been collected yet; automated agents and the project author do not count as
independent user feedback.

Ask three developers unfamiliar with the implementation to:

1. Follow `try-it.md` to install the published PyPI candidate in a clean Python
   3.11+ environment.
2. Run `recallfsck demo` without help from the author.
3. Explain why the buggy race fails and the corrected worker passes.
4. Replay a saved failure and open the HTML evidence.
5. If possible, run the LangChain/Chroma integration and describe what it proves.
6. File their own installation-feedback issue with actual commands and results.

Record platform, version, elapsed setup time, instructions requiring help,
observed outcomes and permission to quote feedback. Do not invent respondents,
post on anyone's behalf or label simulations as independent validation.

Success: several independent developers reproduce the published demos and one
external application team exercises its own integration. The tested LangChain
integration provides real ecosystem API coverage but does not substitute for
an external user's application or feedback.

## Independently maintained application trial

The next major evidence milestone is an application whose ingestion/retrieval
implementation is maintained outside RecallFSCK. A framework library underneath
our own buggy/correct fixtures does not meet that definition.

Use the published package from a clean environment and a disposable test dataset.
Work with the application's maintainer to identify actual acknowledgement,
consistency and authorization semantics. Implement only the adapter and scheduling
hooks needed to observe those paths; record every application change. If a hook
or operation is unavailable, report that limitation rather than declaring PASS.

Record:

- Application repository, immutable revision/version and who maintains it.
- RecallFSCK/Python/backend versions and the exact install commands.
- Source ingestion, replacement, deletion and retrieval APIs actually exercised.
- Adapter and scheduling-hook diff, disposable namespace and cleanup behavior.
- Consistency/monitor windows, operation schedule, observed results and a fresh
  replay. Capture legitimate passing results as well as failures; a discovered
  upstream bug is not a requirement for useful validation.
- Unexercised paths and unsupported scenarios, setup effort, maintainer findings
  and consent before quoting feedback or attributing a bug publicly.

Submit an [external application validation report](https://github.com/sanketsinghai/recallfsck/issues/new?template=external-validation.yml).
Keep issue #8 open until actual reports meet its definition of done. No outreach
or maintainer message is sent merely by preparing this protocol.
