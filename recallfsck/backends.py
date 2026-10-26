"""Owned, disposable stores. No existing collection can be selected."""

import json
import sqlite3
import uuid
from urllib.request import Request, urlopen


class SQLiteIndex:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, text TEXT)")

    def upsert(self, doc_id, text):
        self.db.execute("INSERT OR REPLACE INTO documents VALUES (?, ?)", (doc_id, text))

    def delete(self, doc_id):
        self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def search(self):
        return [row[0] for row in self.db.execute("SELECT id FROM documents ORDER BY id")]

    def inspect(self):
        return self.search()

    def close(self):
        self.db.close()


class QdrantIndex:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.collection = "recallfsck_" + uuid.uuid4().hex
        self.request("PUT", "", {"vectors": {"size": 2, "distance": "Cosine"}})

    def request(self, method, suffix, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(
            self.url + "/collections/" + self.collection + suffix,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=10) as response:
            return json.load(response)["result"]

    def upsert(self, doc_id, text):
        self.request(
            "PUT",
            "/points?wait=true",
            {"points": [{"id": doc_id, "vector": [1.0, 0.0], "payload": {"text": text}}]},
        )

    def delete(self, doc_id):
        self.request("POST", "/points/delete?wait=true", {"points": [doc_id]})

    def search(self):
        result = self.request("POST", "/points/query", {"query": [1.0, 0.0], "limit": 100})
        return sorted(point["id"] for point in result["points"])

    def inspect(self):
        result = self.request("POST", "/points/scroll", {"limit": 100, "with_payload": False})
        return sorted(point["id"] for point in result["points"])

    def close(self):
        self.request("DELETE", "")
