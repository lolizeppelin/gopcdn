import os
import time
import shutil
import inspect
import eventlet

from simpleutil.utils import jsonutils
from simpleutil.utils import singleton
from simpleutil.utils import argutils
from simpleutil.utils import systemutils
from simpleutil.log import log as logging
from simpleutil.config import cfg

from goperation import threadpool
from goperation.utils import safe_func_wrapper
from goperation.manager.api import get_http
from goperation.manager import common as manager_common
from goperation.manager.rpc.agent.application.base import AppEndpointBase

from goperation.manager.utils import resultutils
from goperation.manager.utils import validateutils
from goperation.manager.rpc.exceptions import RpcTargetLockException


from gopcdn import utils
from gopcdn import common
from gopcdn.config import register_opts as reg_base
from gopcdn.deploy.config import register_opts as reg_deploy
from gopcdn.checkout.config import register_opts as reg_checkout
from gopcdn.api.client import GopCdnClient
from gopcdn.deploy import deployer
from gopcdn.checkout import checkouter
from gopcdn.api.rpc.taskflow import create_entity
from gopcdn.api.rpc.taskflow import update_entitys


CONF = cfg.CONF

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
            'auth': {'type': 'object'},
            'cdnhost': {'type': 'object',
                        'required': ['hostname'],
                        'properties': {'hostname': {'type': 'string'},
                                       'listen': {'type': 'integer', 'minimum': 1, 'maxmum': 65535},
                                       'charset': {'type': 'string'},
                                       }},
        }
}


@singleton.singleton
class Application(AppEndpointBase):

    def __init__(self, manager, group):
        if group.name != common.CDN:
            raise TypeError('Endpoint group name error')
        super(Application, self).__init__(manager, group)
        reg_base(group)
        reg_checkout(group)
        reg_deploy(group)
        self.client = GopCdnClient(get_http())
        self.deployer = deployer(CONF[group.name].deployer)

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

    def entity_version(self, entity, impl):
        checker = checkouter(impl)
        return checker.getversion(self.apppath(entity))

    def checkout_entity(self, endpoint, entity, impl, uri, auth, version,
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
            self.deployer.deploy(urlpath=urlpath, cdnhost=cdnhost,
                                 rootpath=self.apppath(entity), configfile=self.location_conf(entity))
            self.client.cdnresource_postlog(entity, body=dict(detail=detail,
                                                              logfile=logfile,
                                                              size_change=size_change,
                                                              start=start,
                                                              end=end,
                                                              result=result))
        threadpool.add_thread(safe_func_wrapper, _checkout, LOG)

    def reset_entity(self, endpoint, entity, impl, uri, auth, version,
                     timeout, cdnhost=None, detail=None):
        self.checkout_entity(endpoint, entity, impl, uri, auth, version,
                             timeout, cdnhost, detail)

    def create_entity(self, endpoint, entity, impl, uri, auth, version,
                      timeout, cdnhost=None, detail=None):
        self._prepare_entity_path(entity)
        self.checkout_entity(endpoint, entity, impl, uri, auth, version,
                             timeout, cdnhost, detail)

    def update_entity(self, entity, impl, auth, version, timeout, detail):
        checker = checkouter(impl)
        logfile = 'cdnresource.%s.%d.log' % ('update', entity)
        with self.lock(entity, 3):
            start = int(time.time())
            result = 'update resource success'
            try:
                size_change = checker.update(auth, version, self.apppath(entity), logfile, timeout)
            except (systemutils.ExitBySIG, systemutils.UnExceptExit):
                result = 'update resource fail'
                size_change = 0
            end = int(time.time())

        def _report():
            self.client.cdnresource_postlog(entity, body=dict(detail=detail, logfile=logfile,
                                                              size_change=size_change,
                                                              start=start, end=end,
                                                              result=result))

        threadpool.add_thread(safe_func_wrapper, _report, LOG)

    def delete_entity(self, entity):
        LOG.info('Try delete %s entity %d' % (self.namespace, entity))
        home = self.entity_home(entity)
        if os.path.exists(home):
            shutil.rmtree(home)
        self.deployer.undeploy(configfile=self.location_conf(entity))

    def rpc_create_entity(self, ctxt, entity, **kwargs):
        esure = kwargs.pop('esure', True)
        with self.lock(entity, timeout=3):
            jsonutils.schema_validate(kwargs, CREATESCHEMA)
            endpoint = validateutils.validate_endpoint(kwargs.pop('forendpoint'))
            kwargs.setdefault('endpoint', endpoint)
            if entity in self.entitys:
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt,
                                                 result='create %s cdn resource fail, entity exist' % endpoint)
            if esure and not self.client.endpoint_count(endpoint)['data'][0].get('count'):
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt,
                                                 result='Endpoint %s not exist, create cdn resource fail' % endpoint)
            middleware = create_entity(self, entity, kwargs)
            if not middleware.success:
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt, result='create %s cdn resource fail' % endpoint)
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             ctxt=ctxt,
                                             result='create %s cdn resource success, waiting checkout finish' %
                                                    endpoint)

    def rpc_delete_entitys(self, ctxt, entitys, **kwargs):
        entitys = argutils.map_to_int(entitys)
        timeout = ctxt.get('deadline')
        while self.frozen:
            if timeout < 1:
                raise RpcTargetLockException(self.namespace, str(entitys), 'endpoint locked')
            eventlet.sleep(1)
            timeout -= 1
        timeout = min(1, timeout)
        try:
            if entitys - self.entitys:
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt, result='delete cdn resource fail, entity not exist')
            while self.locked:
                if not (self.locked & entitys):
                    break
                if timeout < 1:
                    raise RpcTargetLockException(self.namespace, str(entitys), 'endpoint locked')
                eventlet.sleep(1)
                timeout -= 1
            for entity in entitys:
                self.delete_entity(entity)
        finally:
            self.frozen = False

    def rpc_update_entitys(self, ctxt, entitys, **kwargs):
        entitys = argutils.map_to_int(entitys)
        if len(entitys) > 3:
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             resultcode=manager_common.RESULT_ERROR,
                                             ctxt=ctxt, result='update cdn resource fail, '
                                                               'do not update entitys more then 3 once a time')
        timeout = ctxt.get('deadline') - int(time.time())
        if kwargs.get('timeout'):
            timeout = min(timeout, kwargs.get('timeout'))
        kwargs.update({'timeout':  timeout})
        middlewares = update_entitys(self, entitys, kwargs)
        details = []
        success = 0
        for middleware in middlewares:
            if middleware.success:
                success += 1
            details.append(dict(detail_id=middleware.entity,
                                resultcode=manager_common.RESULT_SUCCESS
                                if middleware.success else manager_common.RESULT_ERROR,
                                result=middleware.results))
        if not success:
            resultcode = manager_common.RESULT_ERROR
            result = 'update cdn resource all fail'
        else:
            if success == len(middlewares):
                resultcode = manager_common.RESULT_SUCCESS
                result = 'update cdn resource all success'
            else:
                resultcode = manager_common.RESULT_NOT_ALL_SUCCESS
                result = 'update cdn resource not all success'

        return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                         resultcode=resultcode,
                                         ctxt=ctxt, result=result,
                                         details=details)
