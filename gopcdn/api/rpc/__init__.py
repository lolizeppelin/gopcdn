# -*- coding:utf-8 -*-
import os
import sys
import time
import urllib
import shutil
import contextlib
import functools
import subprocess
import psutil
import eventlet
from eventlet import hubs

from simpleutil.utils import uuidutils
from simpleutil.utils import jsonutils
from simpleutil.utils import singleton
from simpleutil.utils import systemutils
from simpleutil.utils.systemutils import posix
from simpleutil.log import log as logging
from simpleutil.config import cfg

from simpleservice.loopingcall import IntervalLoopinTask

from goperation import threadpool
from goperation.utils import safe_func_wrapper
from goperation.utils import safe_fork
from goperation.manager.api import get_http
from goperation.manager import common as manager_common
from goperation.manager.rpc.agent.application.base import AppEndpointBase

from goperation.manager.utils import resultutils

from gopcdn import common
from gopcdn.deploy.config import register_opts as reg_deploy
from gopcdn.checkout.config import register_opts as reg_checkout
from gopcdn.upload.config import register_opts as reg_upload
from gopcdn.api.client import GopCdnClient
from gopcdn.deploy import deployer
from gopcdn.checkout import checkouter
from gopcdn.upload import uploader


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


CREATENTITYSCHEMA = {
    'type': 'object',
    'properties': {
        'internal': {'type': 'boolean', 'description': '对内CDN在没有域名情况下使用local_ip'},
        'domains': common.DOMAINS,
        'ipaddr': {'type': 'string', 'format': 'ipv4',
                   'description': '指定外网IP, 否则使用全局IP'},
        'character_set': {'type': 'string'},
        'port':  {'type': 'integer',  'minimum': 1, 'maxmum': 65534,}
    }
}


def count_timeout(ctxt, kwargs):
    finishtime = ctxt.get('finishtime')
    timeout = kwargs.pop('timeout', None) if kwargs else None
    if finishtime is None:
        return timeout if timeout is not None else 30
    _timeout = finishtime - int(time.time())
    if timeout is None:
        return _timeout
    return min(_timeout, timeout)


@contextlib.contextmanager
def _empty(*args, **kwargs):
    yield None


class LogCleaner(IntervalLoopinTask):
    """Report Agent online
    """
    def __init__(self, endpoint, days=8):
        self.endpoint = endpoint
        self.last = days*86400
        super(LogCleaner, self).__init__(periodic_interval=3600,
                                         initial_delay=120, stop_on_exception=False)

    def __call__(self, *args, **kwargs):
        overtime = int(time.time()) - self.last
        for entity in self.endpoint.entitys:
            logpath = os.path.join(self.endpoint.logpath(entity))
            try:
                for root, dirs, files in os.walk(logpath):
                    for _file in files:
                        logfile = os.path.join(root, _file)
                        mtime = os.path.getmtime(logfile)
                        if int(mtime) < overtime:
                            os.remove(logfile)
            except (OSError, IOError):
                continue
            eventlet.sleep(0)


@singleton.singleton
class Application(AppEndpointBase):
    """
    gopcdn不管理端口, deploer(nginx/http等)
    所使用端口必须在manager管理端口范围外
    """

    def __init__(self, manager):
        group = CONF.find_group(common.CDN)
        super(Application, self).__init__(manager, group.name)
        # reg_base(group)
        reg_checkout(group)
        reg_deploy(group)
        reg_upload(group)
        self.client = GopCdnClient(get_http())
        self.deployer = deployer(CONF[group.name].deployer)
        for port in self.deployer.ports:
            if self.manager.in_range(port):
                raise ValueError('Deployer port in port range')
        LOG.info('deployer ports %s' % str(self.deployer.ports))
        self.delete_tokens = {}
        self.konwn_domainentitys = {}

    def post_start(self):
        super(Application, self).post_start()
        self.manager.add_periodic_task(LogCleaner(self))
        # reflect entity objtype
        if self.entitys:
            LOG.info('Try reflect entity domain info')
            entity_domain_maps = self.client.cdndomains_shows(entitys=self.entitys)['data']
            if len(entity_domain_maps) != len(self.entitys):
                raise RuntimeError('Entity count error, miss some entity')
            for domaininfo in entity_domain_maps:
                entity = domaininfo.get('entity')
                internal = domaininfo.get('internal')
                port = domaininfo.get('port')
                character_set = domaininfo.get('character_set')
                configfile = self._location_conf(entity)
                domains = domaininfo.get('domains')
                resources = domaininfo.get('resources')
                home = self.apppath(entity)
                LOG.info('Entity %d internal %s' % (entity, internal))
                for domain in domains:
                    LOG.info('Entity %d domain %s' % (entity, domain))
                _resources = []
                for resource in resources:
                    resource_id = resource.pop('resource_id')
                    name = resource.pop('name')
                    etype = resource.pop('etype')
                    rootpath = os.path.join(home, etype, name)

                    if not os.path.exists(rootpath):
                        os.makedirs(rootpath, mode=0775)
                        systemutils.chown(rootpath, self.entity_user(entity), self.entity_group(entity))

                    _resources.append(dict(resource_id=resource_id,
                                           name=name,
                                           etype=etype,
                                           urlpath=urllib.pathname2url(os.path.join(etype, name)),
                                           rootpath=rootpath))
                self.konwn_domainentitys.setdefault(entity,
                                                    dict(internal=internal,
                                                         port=port,
                                                         configfile=configfile,
                                                         listen=self.manager.local_ip if internal else None,
                                                         domains=domains,
                                                         character_set=character_set,
                                                         resources=_resources))
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.debug('domian entitys info: %s' % str(self.konwn_domainentitys))
            LOG.info(str(self.konwn_domainentitys))
            self.deployer.init_conf(maps=self.konwn_domainentitys)

    @property
    def apppathname(self):
        return 'cdnresource'

    @property
    def logpathname(self):
        return 'cdnlog'

    def entity_user(self, entity):
        return 'gopcdn-%d' % entity

    def entity_group(self, entity):
        return 'nginx'

    def _free_ports(self, entity):
        ports = self.manager.allocked_ports.get(common.CDN)[entity]
        self.manager.free_ports(ports)

    def _get_ports(self, entity):
        return list(self.entitys_map[entity])[0]

    def _location_conf(self, entity):
        return os.path.join(self.entity_home(entity), 'location.conf')

    @contextlib.contextmanager
    def _prepare_entity_path(self, entity, **kwargs):
        with super(Application, self)._prepare_entity_path(entity):
            try:
                self.manager.allocked_ports[common.CDN][entity] = set()
                yield
            except Exception:
                LOG.exception('prepare error')
                self.manager.allocked_ports[common.CDN].pop(entity, None)
                raise

    # ----------------resource rpc---------------------
    def _find_resource(self, entity, resource_id):
        resources = self.konwn_domainentitys.get(entity)['resources']
        resource = None
        for r in resources:
            if r['resource_id'] == resource_id:
                resource = r
                break
        if not resource:
            raise ValueError('Resource %d not found' % resource_id)
        rootpath = resource['rootpath']
        if not rootpath.startswith(self.apppath(entity)):
            raise RuntimeError('rootpath is %s, error' % rootpath)
        return resource

    def resource_log_report(self, resource_id, size_change, start, end, result, logfile, detail):

        def _report():
            self.client.cdnresource_postlog(resource_id,
                                            body=dict(detail=detail, logfile=logfile,
                                                      size_change=size_change,
                                                      start=start, end=end, result=result))
        threadpool.add_thread(safe_func_wrapper, _report, LOG)

    def update_resource_version(self, resource_id, version):
        if not version:
            return

        def _update():
            self.client.cdnresource_update(resource_id, body={'version': version})
        threadpool.add_thread(safe_func_wrapper, _update, LOG)

    def checkout_resource(self, entity, resource_id, impl, auth, version, detail, timeout):
        resource = self._find_resource(entity, resource_id)
        rootpath = resource['rootpath']
        checker = checkouter(impl)
        start = int(time.time())
        logfile = '%d.cdnresource.%s.%d.log' % (start, 'checkout', resource_id)
        result = 'upgrade resource success'
        changeuser = functools.partial(systemutils.drop_privileges,
                                       self.entity_user(entity),
                                       self.entity_group(entity))
        try:
            size_change = checker.checkout(auth, version, rootpath,
                                           logfile=os.path.join(self.logpath(entity), logfile),
                                           timeout=timeout, prerun=changeuser)
            self.update_resource_version(resource_id, checker.getversion(rootpath))
        except (systemutils.ExitBySIG, systemutils.UnExceptExit) as e:
            result = 'upgrade resource fail with %s:%s' % (e.__class__.__name__, e.message)
            size_change = 0
        end = int(time.time())
        self.resource_log_report(resource_id, size_change, start, end, result, logfile, detail)

    def rpc_reset_resource(self, ctxt, entity, resource_id,
                             impl, auth, version, detail, **kwargs):
        timeout = count_timeout(ctxt, **kwargs)
        if entity not in self.entitys:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='create cdn resource fail, entity not exist')
        with self.lock(entity, 3):
            resource = self._find_resource(entity, resource_id)
            rootpath = resource['rootpath']
            if os.path.exists(rootpath):
                try:
                    pid = safe_fork()
                    if pid == 0:
                        os.closerange(3, systemutils.MAXFD)
                        shutil.rmtree(rootpath)
                        os._exit(0)
                    posix.wait(pid, timeout)
                except (systemutils.UnExceptExit, systemutils.ExitBySIG):
                    LOG.error('delete %s fail' % rootpath)
                    raise
            os.makedirs(rootpath, mode=0775)
            systemutils.chown(rootpath, self.entity_user(entity), self.entity_group(entity))
            self.checkout_resource(entity, resource_id, impl, auth, version, detail, timeout=timeout)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt,
                                          result='reset cdn resource success')

    def rpc_upgrade_resource(self, ctxt, entity, resource_id,
                             impl, auth, version, detail, **kwargs):
        timeout = count_timeout(ctxt, **kwargs)
        if entity not in self.entitys:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='create cdn resource fail, entity not exist')
        with self.lock(entity, 3):
            self.checkout_resource(entity, resource_id, impl, auth, version, detail, timeout=timeout)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt,
                                          result='upgrade cdn resource success')

    def rpc_delete_resource(self, ctxt, entity, resource_id, **kwargs):
        timeout = count_timeout(ctxt, kwargs)
        if entity not in self.entitys:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='create cdn resource fail, entity not exist')
        with self.lock(entity, 3):
            resource = self._find_resource(entity, resource_id)
            rootpath = resource['rootpath']
            urlpath = resource['urlpath']
            try:
                pid = safe_fork()
                if pid == 0:
                    os.closerange(3, systemutils.MAXFD)
                    shutil.rmtree(rootpath)
                    os._exit(0)
                posix.wait(pid, timeout)
            except (systemutils.UnExceptExit, systemutils.ExitBySIG):
                return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                                  resultcode=manager_common.RESULT_ERROR,
                                                  ctxt=ctxt,
                                                  result='delete cdn resource fail, can remove rootpath catch error')
            else:
                self.deployer.undeploy_resource(entity, urlpath=urlpath)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt,
                                          result='delete cdn resource success')

    def rpc_create_resource(self, ctxt, entity, resource_id, name, etype, **kwargs):
        if entity not in self.entitys:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='create cdn resource fail, entity not exist')
        with self.lock(entity, 3):
            apppath = self.apppath(entity)
            rootpath = os.path.join(apppath, etype, name)
            urlpath = urllib.pathname2url(os.path.join(etype, name))
            configfile = self._location_conf(entity)
            resources = self.konwn_domainentitys.get(entity)['resources']
            if os.path.exists(rootpath):
                return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                                  resultcode=manager_common.RESULT_ERROR,
                                                  ctxt=ctxt,
                                                  result='create cdn resource fail,rootpath exist')
            os.makedirs(rootpath, mode=0775)
            systemutils.chown(rootpath, self.entity_user(entity), self.entity_group(entity))
            try:
                self.deployer.deploy_resource(entity=entity, urlpath=urlpath, rootpath=rootpath,
                                              configfile=configfile)
                resources.append(dict(resource_id=resource_id,
                                      name=name, etype=etype,
                                      urlpath=urlpath,
                                      rootpath=rootpath))
            except Exception:
                shutil.rmtree(rootpath)
                raise
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt, result='create cdn resource success')

    def rpc_upload_resource_file(self, ctxt, entity, resource_id, impl, auth, fileinfo, **kwargs):
        timeout = count_timeout(ctxt, kwargs)
        jsonutils.schema_validate(fileinfo, common.FILEINFOSCHEMA)
        resource = self._find_resource(entity, resource_id)
        rootpath = resource['rootpath']
        logfile = '%d.cdnresource.%s.%d.log' % (int(time.time()), 'upload', resource_id)
        port = max(self.manager.left_ports)
        self.manager.left_ports.remove(port)
        user, group =self.entity_user(entity), self.entity_group(entity)

        domain_info = self.konwn_domainentitys.get(entity)
        if domain_info['internal']:
            ipaddr = self.manager.local_ip
        else:
            ipaddr = self.manager.external_ips[0]

        funcs = []
        store = {'funcs': funcs}

        def _exitfunc():
            eventlet.sleep(0.1)
            for fun in funcs:
                try:
                    fun()
                except Exception:
                    continue
                del funcs[:]

        uper = uploader(impl)
        try:
            uper.prefunc(self)
            uri = uper.upload(store, user=user, group=group,
                                 ipaddr=ipaddr, port=port,
                                 rootpath=rootpath, fileinfo=fileinfo,
                                 logfile=os.path.join(self.logpath(entity), logfile),
                                 exitfunc=_exitfunc,
                                 timeout=timeout)
            funcs.append(lambda : self.left_ports.add(port))
            uper.postfunc(self, store, funcs)
        except Exception:
            self.manager.left_ports.add(port)
            LOG.exception('upload fail')
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt,
                                              result='upload file to cdn resource catch error')
        return resultutils.UriResult(resultcode=manager_common.RESULT_SUCCESS,
                                     result='upload process is waiting',
                                     uri=uri)

    def rpc_delete_resource_file(self, ctxt, entity, resource_id, filename, **kwargs):
        if '..' in filename:
            raise ValueError('filename error')
        resource = self._find_resource(entity, resource_id)
        rootpath = resource['rootpath']
        full_path = os.path.join(rootpath, filename)
        if not os.path.exists(full_path):
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_SUCCESS,
                                              ctxt=ctxt,
                                              result='file not exist in resource %d' % resource_id)
        if os.path.isdir(full_path):
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt,
                                              result='%s is dir' % filename)
        try:
            os.remove(full_path)
        except (OSError, IOError) as e:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt,
                                              result='delete file %s cdn resource %d %s ' % (filename,
                                                                                             resource_id,
                                                                                             e.__class__.__name__))
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt,
                                          result='delete file %s cdn resource %d success' % (filename, resource_id))

    def rpc_list_resource_file(self, ctxt, entity, resource_id, path, deep, **kwargs):
        raise NotImplementedError
        # if '..' in path:
        #     raise ValueError('filename error')
        # resource = self._find_resource(entity, resource_id)
        # rootpath = resource['rootpath']
        # full_path = os.path.join(rootpath, filename)
        # if not path:
        #     path = rootpath

    # ----------------entity rpc---------------------
    def delete_entity(self, entity):
        LOG.info('Try delete %s entity %d' % (self.namespace, entity))
        resources = self.konwn_domainentitys.get(entity)['resources']
        if resources:
            raise ReferenceError('Entity has resources, can not be deleted')
        home = self.entity_home(entity)
        try:
            self.deployer.undeploy_domian(entity)
            if os.path.exists(home):
                shutil.rmtree(home)
        except (systemutils.UnExceptExit, systemutils.ExitBySIG):
            LOG.error('delete %s fail' % home)
            raise
        else:
            self._free_ports(entity)
            self.entitys_map.pop(entity, None)
            self.konwn_domainentitys.pop(entity, None)
            systemutils.drop_user(self.entity_user(entity))

    def rpc_create_entity(self, ctxt, entity, **kwargs):
        with self.lock(entity, timeout=3):
            jsonutils.schema_validate(kwargs, CREATENTITYSCHEMA)
            port = kwargs.get('port', 80)
            if entity in self.entitys:
                return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                                  resultcode=manager_common.RESULT_ERROR,
                                                  ctxt=ctxt,
                                                  result='create %s cdn resource fail, entity exist')
            domains = kwargs.get('domains')
            ipaddr = kwargs.get('ipaddr')
            internal = kwargs.get('internal')
            character_set = kwargs.get('character_set')
            configfile = self._location_conf(entity)
            if not domains and internal:
                listen = self.manager.local_ip
            else:
                if ipaddr:
                    if ipaddr not in self.manager.external_ips:
                        raise ValueError('IP address %s not in agent' % ipaddr)
                    listen = ipaddr
                else:
                    listen = None
            with self._prepare_entity_path(entity):
                self.deployer.deploy_domian(entity, listen=listen, port=port,
                                            charset=kwargs.get('character_set'),
                                            domains=domains)

            self.konwn_domainentitys.setdefault(entity,
                                                dict(internal=kwargs.get('internal'),
                                                     port=port,
                                                     configfile=configfile,
                                                     listen=listen,
                                                     domains=domains,
                                                     character_set=character_set,
                                                     resources=[]))

            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              ctxt=ctxt,
                                              resultcode=manager_common.RESULT_SUCCESS,
                                              result='create domain entity success')

    def rpc_reset_entity(self, ctxt, entity, **kwargs):
        if entity not in self.entitys:
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='reset cdn domain entity fail, entity not exist')
        appath = self.apppath(entity)
        with self.lock(entity, 3):
            self.deployer.clean(entity)
            shutil.rmtree(appath)
            os.makedirs(appath, 0755)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          ctxt=ctxt,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          result='reset %s cdn domain entity finish')

    def rpc_delete_entity(self, ctxt, entity, **kwargs):
        entity = int(entity)
        if entity not in set(self.entitys):
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='delete cdn domain entity fail, entity not exist')
        with self.lock(entity, timeout=3):
            self.delete_entity(entity)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          ctxt=ctxt,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          result='delete cdn domain entity success')

    def rpc_remove_hostnames(self, ctxt, entity, domains):
        """entity domain实体减少hostname绑定"""
        entity = int(entity)
        if entity not in set(self.entitys):
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='remove hostnames of entity fail, entity not exist')
        with self.lock(entity, timeout=3):
            self.deployer.remove_hostnames(entity, domains)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt, result='remove hostnames of entity success')

    def rpc_add_hostnames(self, ctxt, entity, domains):
        """"entity domain实体增加hostname绑定"""
        entity = int(entity)
        if entity not in set(self.entitys):
            return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                              resultcode=manager_common.RESULT_ERROR,
                                              ctxt=ctxt, result='add hostnames of entity fail, entity not exist')
        with self.lock(entity, timeout=3):
            self.deployer.add_hostnames(entity, domains)
        return resultutils.AgentRpcResult(agent_id=self.manager.agent_id,
                                          resultcode=manager_common.RESULT_SUCCESS,
                                          ctxt=ctxt, result='add hostnames of entity success')

    def rpc_deploer_ports(self, ctxt, **kwargs):
        return dict(ports=self.deployer.ports)
