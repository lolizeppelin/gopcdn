from simpleflow.api import load
from simpleflow.storage import Connection
from simpleflow.storage.middleware import LogBook
from simpleflow.engines.engine import ParallelActionEngine


from goperation.manager.rpc.agent.application.taskflow.application import AppCreateBase


from goperation.manager.rpc.agent import sqlite
from goperation.manager.rpc.agent.application.taskflow import pipe
from goperation.manager.rpc.agent.application.taskflow.application import Application



class CdnResourceCreate(AppCreateBase):

    def __init__(self, middleware, data):
        super(CdnResourceCreate, self).__init__(middleware=middleware, revertable=True,
                                                provides='create_entity')

        entity = middleware.entity
        endpoint = data.get('endpoint')
        urlpath = '/%s/%d' % (endpoint, entity)

        self.save_create_kwargs = dict(entity=entity, impl=data.get('impl'),
                                       uri=data['uri'], auth=data['auth'],
                                       version=data['version'], timeout=data.get('timeout', 60),
                                       urlpath=urlpath, cdnhost=data.get('cdnhost'))

        self.save_delete_kwargs = dict(entity=entity, urlpath=urlpath, cdnhost=data.get('cdnhost'))


    def execute(self, **kwargs):
        endpoint = self.middleware.reflection()
        return endpoint.create_entity(**self.save_create_kwargs)


    def revert(self, result, **kwargs):
        endpoint = self.middleware.reflection()
        endpoint.delete_entity(**self.save_delete_kwargs)


def create_entity(middleware, kwargs):
    app = Application(middleware,
                      createtask=CdnResourceCreate(middleware, kwargs))
    book = LogBook(name='create_entity')
    store = dict()
    taskflow_session = sqlite.get_taskflow_session()
    checkout_flow = pipe.flow_factory(taskflow_session, applications=[app, ])
    connection = Connection(taskflow_session)
    engine = load(connection, checkout_flow, store=store,
                  book=book, engine_cls=ParallelActionEngine)
    try:
        engine.run()
        return store
    finally:
        connection.destroy_logbook(book.uuid)

