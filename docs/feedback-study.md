# Independent developer validation

This protocol is ready for volunteers. No independent participant results have
been collected yet; automated agents and the project author do not count as
independent user feedback.

Ask three developers unfamiliar with the implementation to:

1. Install the GitHub release wheel in a clean Python 3.11+ environment.
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
