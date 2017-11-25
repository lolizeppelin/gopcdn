import os
import time
import shutil


from goperation.manager.api import get_http
from goperation.manager.rpc.agent.application.base import AppEndpointBase

from goperation.manager.utils.resultutils import BaseRpcResult
from goperation.manager.rpc.agent.application.taskflow.middleware import EntityMiddleware

from gopcdn.api.client import GopCdnClient
from gopcdn.deploy import deployer
from gopcdn.checkout import checkouter


from gopcdn.api.rpc.taskflow import create_entity

class Application(AppEndpointBase):

    LOGNAMETEMPLATE = 'cdnresource.%d.%d.log'


    def __init__(self, manager, name):
        super(Application, self).__init__(manager, name)
        self.client = GopCdnClient(get_http())

    @property
    def apppathname(self):
        return 'cdnresource'

    @property
    def logpathname(self):
        return 'cdnlog'

    def entity_user(self, entity):
        return 'root'

    def entity_group(self, entity):
        return 'root'

    def location_conf(self, entity):
        return os.path.join(self.entity_home(entity), 'location.conf')

    def create_entity(self, entity, impl, uri, auth, version, timeout,
                       urlpath, cdnhost=None):
        checker = checkouter(impl)
        self._prepare_entity_path(entity)
        logfile = 'cdnresource.create.%d.log' % entity
        size = checker.checkout(uri, auth, version, dst=self.apppath(entity),
                                logfile=os.path.join(self.logpath(entity), logfile),
                                timeout=timeout)
        deployer.deploy(urlpath=urlpath, cdnhost=cdnhost,
                        rootpath=self.apppath(entity), configfile=self.location_conf(entity))
        return logfile, size


    def delete_entity(self, entity, urlpath, cdnhost=None):
        shutil.rmtree(self.endpoint_home(entity))
        deployer.undeploy(urlpath, cdnhost, configfile=self.location_conf(entity))


    def rpc_create_entity(self, ctxt, entity, **kwargs):
        middleware = EntityMiddleware(endpoint=self, entity=entity)
        endpoint = kwargs.get('endpoint')
        detail = kwargs.pop('detail')
        etype = kwargs.pop('etype')
        start = int(time.time())
        store = create_entity(middleware, kwargs)
        logfile, size = store.get('create_entity')
        end = int(time.time())
        self.client.cdnresource_postlog(endpoint, entity, body=dict(detail=detail,
                                                                    etype=etype,
                                                                    impl=kwargs.get('impl'),
                                                                    logfile=logfile,
                                                                    size_change=size,
                                                                    start=start,
                                                                    end=end,
                                                                    ))
        return BaseRpcResult(agent_id=self.manager.agent_id,
                             ctxt=ctxt, result='create %s cdn resource success' % endpoint)

    def rpc_delete_entitys(self, ctxt, entitys, **kwargs):
        for entity in entitys:
            self.delete_entity(entity, None, None)
