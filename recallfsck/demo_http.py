"""A real local HTTP boundary around the tiny ingestion service.

Use: recallfsck test --app examples.http_application:create_application
The adapter owns its server and uses the runner's disposable index.
"""

import asyncio
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.request import Request, urlopen

from recallfsck.stores import Document
from recallfsck.suite import FixtureApplication


class HTTPApplication:
    def __init__(self, store, worker):
        service = FixtureApplication(store, worker)
        self.loop = asyncio.new_event_loop()
        loop = self.loop
        jobs = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    if self.path == "/put":
                        loop.run_until_complete(service.put(Document(**body)))
                        result = None
                    elif self.path == "/delete":
                        loop.run_until_complete(service.delete(**body))
                        result = None
                    elif self.path == "/migrate":
                        loop.run_until_complete(service.migrate())
                        result = None
                    elif self.path == "/start":

                        async def start():
                            paused, resume = asyncio.Event(), asyncio.Event()
                            jobs["resume"] = resume
                            jobs["task"] = asyncio.create_task(service.index("alpha", 42, paused, resume))
                            await asyncio.wait_for(paused.wait(), 5)

                        loop.run_until_complete(start())
                        result = None
                    elif self.path == "/resume":

                        async def resume_job():
                            jobs["resume"].set()
                            await asyncio.wait_for(jobs["task"], 5)

                        loop.run_until_complete(resume_job())
                        result = None
                    elif self.path == "/query":
                        result = service.retrieve(**body)
                    else:
                        self.send_error(404)
                        return
                    encoded = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                except Exception:
                    self.send_error(500, "Synthetic application error")

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            self.server.serve_forever(poll_interval=0.01)
        finally:

            async def cancel_pending():
                tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            self.loop.run_until_complete(cancel_pending())
            self.loop.close()

    def call(self, path, body=None):
        url = f"http://127.0.0.1:{self.server.server_port}" + path
        request = Request(
            url, data=json.dumps(body or {}).encode(), headers={"Content-Type": "application/json"}
        )
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    async def put(self, document):
        self.call("/put", asdict(document))

    async def delete(self, tenant, doc_id):
        self.call("/delete", {"tenant": tenant, "doc_id": doc_id})

    async def migrate(self):
        self.call("/migrate")

    async def index(self, tenant, doc_id, paused, resume):
        self.call("/start")
        paused.set()
        await resume.wait()
        self.call("/resume")

    def retrieve(self, tenant, model):
        return self.call("/query", {"tenant": tenant, "model": model})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def create_application(store, worker):
    return HTTPApplication(store, worker)
