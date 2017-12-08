import os
import time
import shutil
import inspect
import eventlet

from simpleutil.utils import jsonutils
from simpleutil.utils import singleton
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


from gopcdn import common
from gopcdn.deploy.config import register_opts as reg_deploy
from gopcdn.checkout.config import register_opts as reg_checkout
from gopcdn.api.client import GopCdnClient
from gopcdn.deploy import deployer
from gopcdn.deploy.exceptions import DeployError
from gopcdn.checkout import checkouter
from gopcdn.api.rpc.taskflow import create_entity
from gopcdn.api.rpc.taskflow import upgrade_entity


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


CREATESCHEMA = {
    'type': 'object',
    'required': [common.ENDPOINTKEY, 'uri', 'impl'],
    'properties':
        {
            common.ENDPOINTKEY:  {'type': 'string', 'description': 'endpoint name of cdn resource'},
            'impl': {'type': 'string', 'description': 'impl type, svn git nfs'},
            'uri': {'type': 'string', 'description': 'impl checkout uri'},
            'version': {'type': 'string'},
            'auth': {'type': 'object'},
            'esure': {'type': 'boolean'},
            'timeout': {'type': 'integer', 'minimum': 3, 'maxmum': 3600},
            'cdnhost': {'type': 'object',
                        'required': ['hostname'],
                        'properties': {'hostname': {'type': 'string'},
                                       'listen': {'type': 'integer', 'minimum': 1, 'maxmum': 65535},
                                       'charset': {'type': 'string'},
                                       }},
        }
}


def count_timeout(ctxt, kwargs):
    deadline = ctxt.get('deadline')
    timeout = kwargs.get('timeout')
    if deadline is None:
        return timeout
    deadline = deadline - int(time.time())
    if timeout is None:
        return deadline
    return min(deadline, timeout)


@singleton.singleton
class Application(AppEndpointBase):

    def __init__(self, manager):
        group = CONF.find_group(common.CDN)
        super(Application, self).__init__(manager, group.name)
        # reg_base(group)
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

    def resource_log_report(self, entity, size_change, start, end, result, logfile, detail):

        def _report():
            self.client.cdnresource_postlog(entity, body=dict(detail=detail, logfile=logfile,
                                                              size_change=size_change,
                                                              start=start, end=end,
                                                              result=result))
        threadpool.add_thread(safe_func_wrapper, _report, LOG)

    def update_resource_version(self, entity, endpoint, version):
        if not version:
            return

        def _update():
            self.client.cdnresource_update(endpoint, entity, body={'version': version})
        threadpool.add_thread(safe_func_wrapper, _update, LOG)

    def checkout_entity(self, endpoint, entity, impl, uri, auth, version,
                        timeout, cdnhost=None, detail=None):

        caller = inspect.stack()[1][3]
        LOG.debug('checkout call by %s for %s' % (caller, endpoint))
        checker = checkouter(impl)
        logfile = '%d.cdnresource.%s.%d.log' % (int(time.time()), caller.split('_')[0], entity)
        epath = self.apppath(entity)

        def _checkout():
            start = int(time.time())
            result = 'checkout resource success.'
            try:
                size_change = checker.checkout(uri, auth, version, dst=epath,
                                               logfile=os.path.join(self.logpath(entity), logfile),
                                               timeout=timeout)
                self.update_resource_version(entity, endpoint, checker.getversion(epath))
            except Exception as e:
                LOG.exception('checkout catch exception')
                size_change = 0
                result = 'checkout fail %s: %s' % (e.__class__.__name__, str(e))
            end = int(time.time())
            urlpath = '/%s/%d' % (endpoint, entity)
            LOG.info('Deployer %s cdn resource on %s' % (endpoint, urlpath))
            self.deployer.deploy(urlpath=urlpath, cdnhost=cdnhost,
                                 rootpath=epath, configfile=self.location_conf(entity))
            try:
                self.deployer.reload()
            except DeployError as e:
                result += e.message
                raise
            finally:
                self.resource_log_report(entity, size_change, start, end, result, logfile, detail)
        threadpool.add_thread(safe_func_wrapper, _checkout, LOG)

    def create_entity(self, endpoint, entity, impl, uri, auth, version,
                      timeout, cdnhost=None, detail=None):
        self._prepare_entity_path(entity)
        self.checkout_entity(endpoint, entity, impl, uri, auth, version,
                             timeout, cdnhost, detail)
        LOG.info('create_entity success')

    def upgrade_entity(self, endpoint, entity, impl, auth, version, timeout, detail):
        checker = checkouter(impl)
        logfile = '%d.cdnresource.%s.%d.log' % (int(time.time()), 'upgrade', entity)
        epath = self.apppath(entity)
        start = int(time.time())
        result = 'upgrade resource success'
        try:
            size_change = checker.upgrade(auth, version, epath,
                                          os.path.join(self.logpath(entity), logfile),
                                          timeout)
            self.update_resource_version(entity, endpoint, checker.getversion(epath))
        except (systemutils.ExitBySIG, systemutils.UnExceptExit) as e:
            result = 'upgrade resource fail with %s:%s' % (e.__class__.__name__, e.message)
            size_change = 0
        end = int(time.time())
        self.resource_log_report(entity, size_change, start, end, result, logfile, detail)

    def delete_entity(self, entity, **kwargs):
        LOG.info('Try delete %s entity %d' % (self.namespace, entity))
        home = self.entity_home(entity)
        if os.path.exists(home):
            try:
                shutil.rmtree(home)
            except Exception:
                LOG.exception('delete error')
                raise
        self.deployer.undeploy(configfile=self.location_conf(entity))

    def rpc_create_entity(self, ctxt, entity, **kwargs):
        with self.lock(entity, timeout=3):
            jsonutils.schema_validate(kwargs, CREATESCHEMA)
            esure = kwargs.pop('esure', True)
            endpoint = validateutils.validate_endpoint(kwargs.pop(common.ENDPOINTKEY))
            kwargs.setdefault('endpoint', endpoint)
            timeout = count_timeout(ctxt, kwargs)
            kwargs.update({'timeout':  timeout})
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
                resultcode = manager_common.RESULT_ERROR
                result = 'create %s cdn resource fail %s' % (endpoint, str(middleware))
                self.manager.add_entity(self.namespace, entity)
            else:
                resultcode = manager_common.RESULT_SUCCESS
                result = 'create %s cdn resource success, waiting checkout finish' % endpoint

            if kwargs.get('cdnhost'):
                cdnhost = kwargs.get('cdnhost')
                hostname = cdnhost.get('hostname')
                port = cdnhost.get('listen') or self.deployer.listen
            else:
                hostname = self.deployer.hostname
                port = self.deployer.listen
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             ctxt=ctxt,
                                             resultcode=resultcode,
                                             result=result,
                                             details=[dict(detail_id=entity,
                                                      resultcode=resultcode,
                                                      result='%s:%d' % (hostname, port))])

    def rpc_reset_entity(self, ctxt, entity, **kwargs):
        if entity not in self.entitys:
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             resultcode=manager_common.RESULT_ERROR,
                                             ctxt=ctxt, result='reset cdn resource fail, entity not exist')
        jsonutils.schema_validate(kwargs, CREATESCHEMA)
        endpoint = validateutils.validate_endpoint(kwargs.pop(common.ENDPOINTKEY))
        esure = kwargs.pop('esure', True)
        timeout = count_timeout(ctxt, kwargs)
        if esure and not self.client.endpoint_count(endpoint)['data'][0].get('count'):
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             resultcode=manager_common.RESULT_ERROR,
                                             ctxt=ctxt,
                                             result='Endpoint %s not exist, create cdn resource fail' % endpoint)
        checker = checkouter(kwargs.pop('impl'))
        resultcode = manager_common.RESULT_ERROR
        epath = self.apppath(entity)
        with self.lock(entity, 3):
            shutil.rmtree(epath)
            with systemutils.umask():
                os.makedirs(epath)
            logfile = 'cdnresource.reset.%d.log' % entity
            start = int(time.time())
            try:
                size_change = checker.checkout(kwargs.get('uri'), kwargs.get('auth'), kwargs.get('version'),
                                               dst=epath,
                                               logfile=os.path.join(self.logpath(entity), logfile),
                                               timeout=timeout)
                self.update_resource_version(entity, endpoint, kwargs.get('version'))
                result = 'reset cdn resource success'
                resultcode = manager_common.RESULT_SUCCESS
            except Exception as e:
                result = 'reset cdn resource fail with %s' % e.__class__.__name__
                size_change = 0
            self.resource_log_report(entity, size_change, start, int(time.time()),
                                     result, logfile, kwargs.get('detail'))
        return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                         ctxt=ctxt,
                                         resultcode=resultcode,
                                         result='reset %s cdn resource finish',
                                         details=[dict(detail_id=entity,
                                                       resultcode=resultcode,
                                                       result=result)])

    def rpc_delete_entity(self, ctxt, entity, **kwargs):
        entity = int(entity)
        timeout = count_timeout(ctxt, kwargs if kwargs else {})
        while self.frozen:
            if timeout < 1:
                raise RpcTargetLockException(self.namespace, str(entity), 'endpoint locked')
            eventlet.sleep(1)
            timeout -= 1
        timeout = min(1, timeout)
        details = []
        try:
            if entity not in set(self.entitys):
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt, result='delete cdn resource fail, entity not exist')
            while self.locked:
                if entity not in self.lock:
                    break
                if timeout < 1:
                    raise RpcTargetLockException(self.namespace, str(entity), 'endpoint locked')
                eventlet.sleep(1)
                timeout -= 1
            try:
                self.delete_entity(entity)
                resultcode = manager_common.RESULT_SUCCESS
                result = 'delete %d success' % entity
            except Exception as e:
                resultcode = manager_common.RESULT_ERROR
                result = 'delete %d fail with %s' % (entity, e.__class__.__name__)
            details.append(dict(detail_id=entity,
                                resultcode=resultcode,
                                result=result))
        finally:
            self.frozen = False
        return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                         ctxt=ctxt,
                                         resultcode=resultcode,
                                         result=result,
                                         details=details)

    def rpc_upgrade_entity(self, ctxt, entity, **kwargs):
        entity = int(entity)
        timeout = count_timeout(ctxt, kwargs)
        kwargs.update({'timeout':  timeout})
        endpoint = validateutils.validate_endpoint(kwargs.pop(common.ENDPOINTKEY))
        esure = kwargs.pop('esure', True)
        kwargs.setdefault('endpoint', endpoint)
        with self.lock(entity, 3):
            middleware = upgrade_entity(self, entity, kwargs)
        if entity not in self.entitys:
            return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                             resultcode=manager_common.RESULT_ERROR,
                                             ctxt=ctxt, result='upgrade cdn resource fail, entity not exist')
        if esure and not self.client.endpoint_count(endpoint)['data'][0].get('count'):
                return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                                 resultcode=manager_common.RESULT_ERROR,
                                                 ctxt=ctxt,
                                                 result='Endpoint %s not exist, upgrade '
                                                        'cdn resource fail' % endpoint)
        if not middleware.success:
            resultcode = manager_common.RESULT_ERROR
            result = 'upgrade %s cdn resource fail %s' % (endpoint, str(middleware))
        else:
            resultcode = manager_common.RESULT_SUCCESS
            result = 'upgrade %s cdn resource success' % endpoint
        return resultutils.BaseRpcResult(agent_id=self.manager.agent_id,
                                         ctxt=ctxt,
                                         resultcode=resultcode,
                                         result=result,
                                         details=[dict(detail_id=middleware.entity,
                                                       resultcode=resultcode,
                                                       result=result)])
