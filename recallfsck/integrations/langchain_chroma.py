"""LangChain Chroma ingestion and retrieval on an owned disposable collection.

The scheduling fixture is ours. Writes, deletes, embeddings and retrieval go
through the real langchain-chroma package, while index inspection is independent.
This is an integration example, not a claim of an upstream LangChain bug.
"""

import json
from dataclasses import asdict

from recallfsck.stores import ChromaStore, Document, ordered
from recallfsck.suite import FixtureApplication


class LangChainBridge:
    def __init__(self, store):
        from langchain_chroma import Chroma
        from langchain_core.embeddings import Embeddings

        class SyntheticEmbeddings(Embeddings):
            def embed_documents(self, texts):
                return [Document(**json.loads(text)).vector for text in texts]

            def embed_query(self, text):
                return Document(model=text).vector

        self.vectorstore = Chroma(
            client=store.client,
            collection_name=store.name,
            embedding_function=SyntheticEmbeddings(),
            create_collection_if_not_exists=False,
        )

    def upsert(self, document):
        from langchain_core.documents import Document as LangChainDocument

        self.vectorstore.add_documents(
            [LangChainDocument(page_content=json.dumps(asdict(document)), metadata=asdict(document))],
            ids=[document.key],
        )

    def delete(self, tenant, doc_id):
        self.vectorstore.delete(ids=[f"{tenant}:{doc_id}"])

    def query(self, tenant, model):
        results = self.vectorstore.similarity_search_by_vector_with_relevance_scores(
            embedding=Document(model=model).vector,
            k=100,
            filter={"$and": [{"tenant": tenant}, {"model": model}]},
        )
        # This vector-specific API returns cosine distances, where lower is better.
        return ordered([dict(document.metadata) for document, distance in results if distance <= 0.1])


def create_application(store, worker):
    if not isinstance(store, ChromaStore):
        raise ValueError("LangChain Chroma integration requires --backend chroma")
    return FixtureApplication(LangChainBridge(store), worker)
