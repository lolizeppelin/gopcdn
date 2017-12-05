from simpleutil.log import log as logging

from simpleflow.api import load
from simpleflow.types import failure
from simpleflow.storage import Connection
from simpleflow.storage.middleware import LogBook
from simpleflow.engines.engine import ParallelActionEngine


from goperation.taskflow import common
from goperation.manager.rpc.agent.application.taskflow.middleware import EntityMiddleware
from goperation.manager.rpc.agent.application.taskflow.application import AppCreateBase
from goperation.manager.rpc.agent.application.taskflow.application import AppUpdateBase


from goperation.manager.rpc.agent import sqlite
from goperation.manager.rpc.agent.application.taskflow import pipe
from goperation.manager.rpc.agent.application.taskflow.application import Application as ApplicationTask


from gopcdn.api.rpc import Application

LOG = logging.getLogger(__name__)


class CdnResourceCreate(AppCreateBase):

    def __init__(self, middleware, data):
        super(CdnResourceCreate, self).__init__(middleware=middleware, revertable=True)

        entity = middleware.entity
        endpoint=data.get('endpoint')
        detail = data.pop('detail', None)
        etype = data.pop('etype')

        self.save_create_kwargs = dict(endpoint=endpoint,
                                       entity=entity, impl=data.get('impl', 'svn'),
                                       uri=data['uri'], auth=data.get('auth'),
                                       version=data.get('version'), etype=etype,
                                       timeout=data.get('timeout', 300),
                                       cdnhost=data.get('cdnhost'),
                                       detail=detail)

        self.save_delete_kwargs = dict(endpoint=endpoint, entity=entity, cdnhost=data.get('cdnhost'))
        self.result = None

    def execute(self, **kwargs):
        if self.middleware.is_success(self.__class__.__name__) \
                and not self.rollback:
            return
        endpoint = self.middleware.reflection()
        self.result = endpoint.create_entity(**self.save_create_kwargs)
        return self.result

    def revert(self, result, **kwargs):
        super(CdnResourceCreate, self).revert(result, **kwargs)
        if isinstance(result, failure.Failure) or self.rollback:
            LOG.info('Create fail, try revert')
            endpoint = self.middleware.reflection()
            endpoint.delete_entity(**self.save_delete_kwargs)
            self.middleware.set_return(self.__class__.__name__, common.REVERTED)


class CdnResourceUpdate(AppUpdateBase):
    pass



def create_entity(endpoint, entity, kwargs):
    middleware = EntityMiddleware(endpoint=endpoint,
                                  entity=entity)
    app = ApplicationTask(middleware,
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
        return middleware
    finally:
        connection.destroy_logbook(book.uuid)


def update_entitys(endpoint, entitys, kwargs):
    middlewares = []
    applications = []
    for entity in entitys:
        middleware = EntityMiddleware(endpoint=endpoint, entity=entity)
        middlewares.append(middleware)
        applications.append(ApplicationTask(middleware, updatetask=CdnResourceUpdate(middleware, kwargs)))
    book = LogBook(name='update_entitys')
    store = dict()
    taskflow_session = sqlite.get_taskflow_session()
    checkout_flow = pipe.flow_factory(taskflow_session, applications=applications)
    connection = Connection(taskflow_session)
    engine = load(connection, checkout_flow, store=store,
                  book=book, engine_cls=ParallelActionEngine)
    try:
        engine.run()
        return middlewares
    finally:
        connection.destroy_logbook(book.uuid)
