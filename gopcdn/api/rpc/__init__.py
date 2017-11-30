import os
import time
import shutil
import inspect

from simpleutil.utils import jsonutils
from simpleutil.log import log as logging

from goperation import threadpool
from goperation.utils import safe_func_wrapper
from goperation.manager.api import get_http
from goperation.manager import common as manager_common
from goperation.manager.rpc.agent.application.base import AppEndpointBase

from goperation.manager.utils import resultutils
from goperation.manager.utils import validateutils
from goperation.manager.rpc.agent.application.taskflow.middleware import EntityMiddleware

from gopcdn.api.client import GopCdnClient
from gopcdn.deploy import deployer
from gopcdn.checkout import checkouter
from gopcdn import utils
from gopcdn import common


from gopcdn.api.rpc.taskflow import create_entity

LOG = logging.getLogger(__name__)


CREATESCHEMA = {
    'type': 'object',
    'required': ['forendpoint', 'etype', 'uri'],
    'properties':
        {
            'cdnfor':  {'type': 'string', 'description': 'endpoint name of cdn resource'},
            'etype': {'oneOf': [{'type': 'string', 'enum': common.InvertEntityTypeMap.keys()},
                                {'type': 'integer', 'enum': common.EntityTypeMap.keys()}],
                      'description': 'entity type, ios,android'},
            'impl': {'type': 'string', 'description': 'impl type, svn git nfs'},
            'uri': {'type': 'string', 'description': 'impl checkout uri'},
            'version': {'type': 'string'},
            'timeout': {'type': 'integer', 'minimum': 10, 'maxmum': 3600,
                        'description': 'impl checkout timeout'},
            'auth': {'type': 'object'},
            'cdnhost': {'type': 'object',
                        'required': ['hostname'],
                        'properties': {'hostname': {'type': 'string'},
                                       'listen': {'type': 'integer', 'minimum': 1, 'maxmum': 65535},
                                       'charset': {'type': 'string'},
                                       }},
        }
}


class Application(AppEndpointBase):

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

    def checkout_entity(self, endpoint, entity, impl, uri, auth, version, etype,
                     timeout, cdnhost=None, detail=None):

        caller = inspect.stack()[1][3]
        LOG.debug('checkout call by %s for %s' % (caller, endpoint))
        checker = checkouter(impl)
        logfile = 'cdnresource.%s.%d.log' % (caller.split('_')[0], entity)
        def _checkout():
            start = int(time.time())
            result = 'checkout resource success'
            try:
                size_change = checker.checkout(uri, auth, version, dst=self.apppath(entity),
                                               logfile=os.path.join(self.logpath(entity), logfile),
                                               timeout=timeout)
            except Exception as e:
                LOG.exception('checkout catch exception')
                size_change = 0
                result = 'checkout fail %s: %s' % (e.__class__.__name__, str(e))
            end = int(time.time())
            urlpath = '/%s/%d' % (endpoint, entity)
            LOG.info('Deployer %s cdn resource on %s' % (endpoint, urlpath))
            deployer.deploy(urlpath=urlpath, cdnhost=cdnhost,
                            rootpath=self.apppath(entity), configfile=self.location_conf(entity))
            self.client.cdnresource_postlog(endpoint, entity, body=dict(detail=detail,
                                                                        etype=etype,
                                                                        impl=impl,
                                                                        logfile=logfile,
                                                                        size_change=size_change,
                                                                        start=start,
                                                                        end=end,
                                                                        result=result,
                                                                        ))
        threadpool.add_thread(safe_func_wrapper, _checkout, LOG)
        return logfile

    def reset_entity(self, endpoint, entity, impl, uri, auth, version, etype,
                     timeout, cdnhost=None, detail=None):
        self.checkout_entity(endpoint, entity, impl, uri, auth, version, etype,
                             timeout, cdnhost, detail)


    def create_entity(self, endpoint, entity, impl, uri, auth, version, etype,
                      timeout, cdnhost=None, detail=None):
        self._prepare_entity_path(entity)
        self.checkout_entity(endpoint, entity, impl, uri, auth, version, etype,
                             timeout, cdnhost, detail)


    def delete_entity(self, entity):
        LOG.info('Try delete %s entity %d' % (self.namespace, entity))
        home = self.entity_home(entity)
        if os.path.exists(home):
            shutil.rmtree(home)
        deployer.undeploy(configfile=self.location_conf(entity))

    def rpc_create_entity(self, ctxt, entity, **kwargs):
        jsonutils.schema_validate(kwargs, CREATESCHEMA)
        etype = utils.validate_etype(kwargs.pop('etype'))
        endpoint = validateutils.validate_endpoint(kwargs.pop('forendpoint'))
        kwargs.setdefault('endpoint', endpoint)
        kwargs.setdefault('etype', etype)
        # TODO for test
        # if not self.client.endpoint_count(endpoint)['data'][0].get('count'):
        #     return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
        #                                      resultcode=manager_common.RESULT_ERROR,
        #                                      ctxt=ctxt,
        #                                      result='Endpoint %s not exist, create cdn resource fail' % endpoint)
        middleware = EntityMiddleware(endpoint=self, entity=entity)
        create_entity(middleware, kwargs)
        if not middleware.success:
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             resultcode=manager_common.RESULT_ERROR,
                                             ctxt=ctxt, result='create %s cdn resource fail' % endpoint)
        return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                         ctxt=ctxt,
                                         result='create %s cdn resource success, waiting checkout finish' % endpoint)

    def rpc_delete_entitys(self, ctxt, entitys, **kwargs):
        for entity in entitys:
            self.delete_entity(entity)
