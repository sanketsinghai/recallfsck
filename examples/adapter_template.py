"""Copy this contract into your application integration package.

The factory is explicitly loaded using --app your_package.module:create_application.
Methods must call the real application and use the provided disposable store.
Do not compute retrieval results from the expected state or hide failures.
"""


class ApplicationAdapter:
    def __init__(self, store, worker):
        self.store = store
        raise NotImplementedError("Connect the application's disposable test namespace")

    async def put(self, document):
        raise NotImplementedError("Acknowledge the real application's write")

    async def delete(self, tenant, doc_id):
        raise NotImplementedError("Delete through the application")

    async def migrate(self):
        raise NotImplementedError("Re-embed existing documents using model v2")

    async def index(self, tenant, doc_id, paused, resume):
        raise NotImplementedError("Signal paused before commit; await resume; finish worker")

    def retrieve(self, tenant, model):
        raise NotImplementedError("Return actual document records from application retrieval")

    def close(self):
        """Release application resources; runner removes its own store afterward."""


def create_application(store, worker):
    return ApplicationAdapter(store, worker)
