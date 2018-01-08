import copy
from simpleutil.log import log as logging

from simpleflow.api import load
from simpleflow.types import failure
from simpleflow.storage import Connection
from simpleflow.storage.middleware import LogBook
from simpleflow.engines.engine import ParallelActionEngine


from goperation.taskflow import common
from goperation.manager.rpc.agent.application.taskflow.middleware import EntityMiddleware
from goperation.manager.rpc.agent.application.taskflow.application import AppCreateBase
from goperation.manager.rpc.agent.application.taskflow.application import AppFileUpgradeBase


from goperation.manager.rpc.agent import sqlite
from goperation.manager.rpc.agent.application.taskflow import pipe
from goperation.manager.rpc.agent.application.taskflow.application import Application as ApplicationTask


LOG = logging.getLogger(__name__)


class CdnResourceCreate(AppCreateBase):

    def __init__(self, middleware, data):
        super(CdnResourceCreate, self).__init__(middleware=middleware, revertable=True)

        entity = middleware.entity
        endpoint = data.get('endpoint')
        detail = data.pop('detail', None)

        self.save_create_kwargs = dict(endpoint=endpoint,
                                       entity=entity, impl=data.get('impl', 'svn'),
                                       uri=data['uri'], auth=data.get('auth'),
                                       version=data.get('version'),
                                       timeout=data.get('timeout', 300),
                                       cdnhost=data.get('cdnhost'),
                                       detail=detail)

        self.save_delete_kwargs = dict(endpoint=endpoint, entity=entity, cdnhost=data.get('cdnhost'))
        self.result = None

    def execute(self):
        if self.middleware.is_success(self.taskname) \
                and not self.rollback:
            return
        endpoint = self.middleware.reflection()
        endpoint.create_entity(**self.save_create_kwargs)

    def revert(self, result, **kwargs):
        super(CdnResourceCreate, self).revert(result, **kwargs)
        if isinstance(result, failure.Failure) or self.rollback:
            if isinstance(result, failure.Failure):
                LOG.debug(result.pformat(traceback=True))
            endpoint = self.middleware.reflection()
            endpoint.delete_entity(**self.save_delete_kwargs)
            self.middleware.set_return(self.taskname, common.REVERTED)


class CdnResourceUpgrade(AppFileUpgradeBase):

    def __init__(self, middleware, data):
        super(CdnResourceUpgrade, self).__init__(middleware=middleware, revertable=False)
        entity = middleware.entity
        self.save_kwargs = dict(entity=entity,
                                endpoint=data.get('endpoint'),
                                impl=data.get('impl'),
                                auth=data.get('auth'),
                                version=data.get('version'),
                                timeout=data.get('timeout', 300),
                                detail=data.get('detail'))
        self.lastversion = None

    def execute(self):
        if self.middleware.is_success(self.taskname) \
                and not self.rollback:
            return
        endpoint = self.middleware.reflection()
        self.lastversion = endpoint.entity_version(self.save_kwargs.get('entity'),
                                                   self.save_kwargs.get('impl'))
        return endpoint.upgrade_entity(**self.save_kwargs)

    def revert(self, result, **kwargs):
        super(CdnResourceUpgrade, self).revert(result, **kwargs)
        if isinstance(result, failure.Failure) or self.rollback:
            LOG.info('Upgrade fail, try revert')
            LOG.debug(result.pformat(traceback=True))
            if not self.lastversion:
                self.middleware.set_return(self.taskname, common.NOT_EXECUTED)
                return
            endpoint = self.middleware.reflection()
            revert_kwargs = copy.deepcopy(self.save_kwargs)
            revert_kwargs['version'] = self.lastversion
            endpoint.upgrade_entity(**revert_kwargs)
            self.middleware.set_return(self.taskname, common.REVERTED)


def create_entity(appendpoint, entity, kwargs):
    middleware = EntityMiddleware(endpoint=appendpoint,
                                  entity=entity)
    app = ApplicationTask(middleware,
                          createtask=CdnResourceCreate(middleware, kwargs))
    book = LogBook(name='create_entity_%d' % entity)
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
        LOG.info('create middleware result %s' % str(middleware))
        connection.destroy_logbook(book.uuid)


def upgrade_entity(appendpoint, entity, kwargs):
    middleware = EntityMiddleware(endpoint=appendpoint, entity=entity)
    app = ApplicationTask(middleware, upgradetask=CdnResourceUpgrade(middleware, kwargs))
    book = LogBook(name='upgrade_entity_%d' % entity)
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
        LOG.info('upgrade middleware result %s' % str(middleware))
        connection.destroy_logbook(book.uuid)
