import os

from simpleflow.api import load
from simpleflow.storage import Connection
from simpleflow.engines.engine import ParallelActionEngine

from simpleservice.rpc.target import Target

from goperation.manager import targetutils
from goperation.manager.rpc.agent.application.base import AppEndpointBase

from goperation.manager.rpc.agent import sqlite
from goperation.manager.rpc.agent.application.taskflow import pipe
from goperation.manager.rpc.agent.application.taskflow.application import Application as App
from goperation.manager.rpc.agent.application.taskflow.middleware import EntityMiddleware

from gopcdn import common
from gopcdn.deploy import deployer

class Application(AppEndpointBase):


    def __init__(self, manager, name):
        super(Application, self).__init__(manager, name)

    def appname(self, entity):
        return 'cdnresource'

    def appnpath(self, entity):
        return os.path.join(self.entity_home(entity), self.appname(entity))

    def entity_user(self, entity):
        return 'gopcdn'

    def entity_group(self, entity):
        return 'gopcdn'

    def location_conf(self, entity):
        return os.path.join(self.entity_home(entity), 'location.conf')

    def rpc_create_entity(self, entity, **kwargs):

        version = kwargs['version']
        cdnhost = kwargs['cdnhost']
        impl = kwargs['impl']
        uri = kwargs['uri']
        auth = kwargs['auth']
        detail = kwargs['detail']

        urlpath = '/%s/%d' % (kwargs['endpoint'], entity)


        application = App(updatefunc=1, update_kwargs={'mark': mark})
        middleware = EntityMiddleware(endpoint=self, entity=entity,
                                      application=application)
        taskflow_session = sqlite.get_taskflow_session()
        checkout_flow = pipe.flow_factory(taskflow_session, middlewares=[middleware])
        connection = Connection(taskflow_session)
        engine = load(connection, checkout_flow, engine_cls=ParallelActionEngine)
        result = engine.run()
        deployer.deploy(urlpath=urlpath,
                        rootpath=self.appnpath(entity), configfile=self.location_conf(entity),
                        hostinfo=None)

    def rpc_delete_entitys(self, entitys, **kwargs):
        pass

    def rpc_checkout_resource(self, entity, mark, backup=False):
        application = App(updatefunc=1, update_kwargs={'mark': mark},
                          startfunc=2)
        middleware = EntityMiddleware(endpoint=self, entity=entity,
                                      application=application)
        taskflow_session = sqlite.get_taskflow_session()
        main_flow = pipe.flow_factory(taskflow_session, middlewares=[middleware])
        connection = Connection(taskflow_session)
        engine = load(connection, main_flow, engine_cls=ParallelActionEngine)
        result = engine.run()