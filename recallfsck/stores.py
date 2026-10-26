"""Disposable document/vector stores used by the version-2 suite.

All rows returned by an adapter are actual backend observations. Synthetic
embeddings intentionally avoid network models and nondeterministic generation.
"""

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from typing import Protocol

from .backends import QdrantIndex


@dataclass(frozen=True)
class Document:
    id: int = 42
    tenant: str = "alpha"
    text: str = "original fact"
    revision: int = 1
    model: str = "v1"

    @property
    def key(self):
        return f"{self.tenant}:{self.id}"

    @property
    def vector(self):
        return [1.0, 0.0] if self.model == "v1" else [0.0, 1.0]


class Store(Protocol):
    def upsert(self, document: Document) -> None: ...
    def delete(self, tenant: str, doc_id: int) -> None: ...
    def scan(self) -> list[dict]: ...
    def query(self, tenant: str, model: str) -> list[dict]: ...
    def close(self) -> None: ...


def ordered(rows):
    return sorted(rows, key=lambda row: (row["tenant"], row["id"]))


class SQLiteStore:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE TABLE docs (tenant TEXT, id INTEGER, body TEXT, PRIMARY KEY (tenant,id))")

    def upsert(self, document):
        self.db.execute(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?)",
            (document.tenant, document.id, json.dumps(asdict(document))),
        )

    def delete(self, tenant, doc_id):
        self.db.execute("DELETE FROM docs WHERE tenant=? AND id=?", (tenant, doc_id))

    def scan(self):
        return ordered([json.loads(row[0]) for row in self.db.execute("SELECT body FROM docs")])

    def query(self, tenant, model):
        # SQL filtering is real, but this backend does not claim vector search.
        rows = self.db.execute("SELECT body FROM docs WHERE tenant=?", (tenant,))
        return ordered([doc for row in rows if (doc := json.loads(row[0]))["model"] == model])

    def close(self):
        self.db.close()


class QdrantStore(QdrantIndex):
    @staticmethod
    def point_id(tenant, doc_id):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"recallfsck:{tenant}:{doc_id}"))

    def upsert(self, document):
        self.request(
            "PUT",
            "/points?wait=true",
            {
                "points": [
                    {
                        "id": self.point_id(document.tenant, document.id),
                        "vector": document.vector,
                        "payload": asdict(document),
                    }
                ]
            },
        )

    def delete(self, tenant, doc_id):
        self.request("POST", "/points/delete?wait=true", {"points": [self.point_id(tenant, doc_id)]})

    def scan(self):
        rows, offset = [], None
        while True:
            body = {"limit": 100, "with_payload": True}
            if offset is not None:
                body["offset"] = offset
            result = self.request("POST", "/points/scroll", body)
            rows.extend(point["payload"] for point in result["points"])
            offset = result.get("next_page_offset")
            if offset is None:
                return ordered(rows)

    def query(self, tenant, model):
        result = self.request(
            "POST",
            "/points/query",
            {
                "query": Document(model=model).vector,
                "limit": 100,
                "with_payload": True,
                "score_threshold": 0.9,
                "filter": {
                    "must": [
                        {"key": "tenant", "match": {"value": tenant}},
                        {"key": "model", "match": {"value": model}},
                    ]
                },
            },
        )
        return ordered([point["payload"] for point in result["points"]])


class ChromaStore:
    def __init__(self):
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        self.name = "recallfsck_" + uuid.uuid4().hex
        self.collection = self.client.create_collection(
            self.name, embedding_function=None, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, document):
        self.collection.upsert(
            ids=[document.key],
            embeddings=[document.vector],
            metadatas=[asdict(document)],
            documents=[document.text],
        )

    def delete(self, tenant, doc_id):
        self.collection.delete(ids=[f"{tenant}:{doc_id}"])

    def scan(self):
        return ordered(self.collection.get(include=["metadatas"])["metadatas"])

    def query(self, tenant, model):
        count = self.collection.count()
        if not count:
            return []
        result = self.collection.query(
            query_embeddings=[Document(model=model).vector],
            n_results=min(count, 100),
            where={"$and": [{"tenant": tenant}, {"model": model}]},
            include=["metadatas", "distances"],
        )
        return ordered(
            [row for row, distance in zip(result["metadatas"][0], result["distances"][0]) if distance <= 0.1]
        )

    def close(self):
        self.client.delete_collection(self.name)


class PgvectorStore:
    def __init__(self, dsn):
        import psycopg
        from psycopg import sql

        self.conn = psycopg.connect(dsn, autocommit=True, connect_timeout=10)
        self.name = "recallfsck_" + uuid.uuid4().hex
        self.table = sql.Identifier(self.name)
        try:
            # Extension installation belongs to server setup, not the test adapter.
            self.conn.execute(
                sql.SQL(
                    "CREATE TABLE {} (tenant TEXT, id BIGINT, body JSONB, "
                    "embedding vector(2), PRIMARY KEY(tenant,id))"
                ).format(self.table)
            )
        except BaseException:
            self.conn.close()
            raise

    def upsert(self, document):
        from psycopg import sql
        from psycopg.types.json import Jsonb

        self.conn.execute(
            sql.SQL(
                "INSERT INTO {} VALUES (%s,%s,%s,%s::vector) "
                "ON CONFLICT (tenant,id) DO UPDATE SET body=EXCLUDED.body, embedding=EXCLUDED.embedding"
            ).format(self.table),
            (document.tenant, document.id, Jsonb(asdict(document)), json.dumps(document.vector)),
        )

    def delete(self, tenant, doc_id):
        from psycopg import sql

        self.conn.execute(
            sql.SQL("DELETE FROM {} WHERE tenant=%s AND id=%s").format(self.table), (tenant, doc_id)
        )

    def scan(self):
        from psycopg import sql

        return ordered(
            [row[0] for row in self.conn.execute(sql.SQL("SELECT body FROM {}").format(self.table))]
        )

    def query(self, tenant, model):
        from psycopg import sql

        rows = self.conn.execute(
            sql.SQL(
                "SELECT body FROM {} WHERE tenant=%s AND body->>'model'=%s "
                "AND (embedding <=> %s::vector) < 0.1 ORDER BY embedding <=> %s::vector LIMIT 100"
            ).format(self.table),
            (
                tenant,
                model,
                json.dumps(Document(model=model).vector),
                json.dumps(Document(model=model).vector),
            ),
        )
        return ordered([row[0] for row in rows])

    def close(self):
        from psycopg import sql

        try:
            self.conn.execute(sql.SQL("DROP TABLE {}").format(self.table))
        finally:
            self.conn.close()


def store_factory(backend, url=None):
    if backend == "sqlite":
        return SQLiteStore
    if backend == "qdrant":
        return lambda: QdrantStore(url or "http://localhost:6333")
    if backend == "chroma":
        return ChromaStore
    if backend == "pgvector":
        if not url:
            raise ValueError("pgvector requires a DSN via RECALLFSCK_URL or --url")
        return lambda: PgvectorStore(url)
    raise ValueError(f"Unknown backend: {backend}")
