# Launch draft

Suggested title:

Show HN: RecallFSCK — replayable lifecycle checks for RAG indexes

Draft text:

I built a developer test utility for a frustrating failure: a delete succeeds,
but an older ingestion worker finishes afterward and restores the document to
search. RecallFSCK pauses that worker, completes deletion, resumes indexing, then
compares real application retrieval and index contents with a reference model.

The demonstration contains a deliberately broken worker and a corrected worker.
It is not a newly discovered upstream bug. The same schedules run on SQLite,
Qdrant, Chroma and pgvector. A LangChain/Chroma integration exercises actual
LangChain ingestion, deletion, embeddings and retrieval APIs.

The tool saves JSON reproductions, HTML evidence and JUnit results. It includes
stateful discovery/shrinking and configurable finite observation windows. It does
not prove physical erasure, arbitrary distributed safety or indefinite absence.

Code and reproducible installation:
https://github.com/sanketsinghai/recallfsck

I would welcome actual installation feedback and examples of lifecycle problems
in disposable test environments. Reports containing private documents or secrets
should not be posted publicly.

This is a prepared draft, not a claim that a post was submitted or feedback was
received. Outreach requires the owner's explicit choice of audience and channel.
