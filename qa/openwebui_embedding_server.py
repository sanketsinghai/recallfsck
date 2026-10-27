"""Local-only deterministic embedding provider for the Open WebUI trial.

No LLM, paid service or semantic-quality claim. Run as a sidecar without exposed
host ports. The tested application still performs its own extraction, chunking,
indexing, API authorization, vector retrieval and deletion.
"""

import hashlib
import json
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def embedding(text):
    vector = [0.0] * 64
    for token in re.findall(r"\w+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:2], "big") % 64] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1
    return [value / norm for value in vector]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b'{"status":"ready"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        texts = payload.get("input", [])
        if isinstance(texts, str):
            texts = [texts]
        body = json.dumps(
            {
                "object": "list",
                "model": "recallfsck-synthetic-v1",
                "data": [
                    {"object": "embedding", "index": index, "embedding": embedding(text)}
                    for index, text in enumerate(texts)
                ],
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
