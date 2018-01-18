# -*- coding:utf-8 -*-
import os
import six
import time
import eventlet
import inspect
import webob.exc

from sqlalchemy.sql import and_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from simpleutil.common.exceptions import InvalidArgument
from simpleutil.log import log as logging
from simpleutil.utils import jsonutils
from simpleutil.utils import timeutils
from simpleutil.utils import singleton
from simpleutil.utils import argutils
from simpleservice.ormdb.api import model_query
from simpleservice.ormdb.api import model_count_with_key
from simpleservice.rpc.exceptions import AMQPDestinationNotFound
from simpleservice.rpc.exceptions import MessagingTimeout
from simpleservice.rpc.exceptions import NoSuchMethod

from goperation import threadpool
from goperation.utils import safe_func_wrapper
from goperation.manager import common as manager_common
from goperation.manager.notify import NOTIFYSCHEMA
from goperation.manager.utils import resultutils
from goperation.manager.utils import targetutils
from goperation.manager.api import get_client
from goperation.manager.api import rpcfinishtime
from goperation.manager.exceptions import CacheStoneError
from goperation.manager.wsgi.entity.controller import EntityReuest
from goperation.manager.wsgi.contorller import BaseContorller
from goperation.manager.wsgi.exceptions import RpcPrepareError
from goperation.manager.wsgi.exceptions import RpcResultError


from gopcdn import common
from gopcdn.api import endpoint_session
from gopcdn.models import CdnDomain
from gopcdn.models import Domain
from gopcdn.models import CdnResource
from gopcdn.models import CheckOutLog
from gopcdn.models import ResourceQuote


safe_dumps = jsonutils.safe_dumps_as_bytes
safe_loads = jsonutils.safe_loads_as_bytes

LOG = logging.getLogger(__name__)

FAULT_MAP = {InvalidArgument: webob.exc.HTTPClientError,
             NoSuchMethod: webob.exc.HTTPNotImplemented,
             AMQPDestinationNotFound: webob.exc.HTTPServiceUnavailable,
             MessagingTimeout: webob.exc.HTTPServiceUnavailable,
             RpcResultError: webob.exc.HTTPInternalServerError,
             CacheStoneError: webob.exc.HTTPInternalServerError,
             RpcPrepareError: webob.exc.HTTPInternalServerError,
             NoResultFound: webob.exc.HTTPNotFound,
             MultipleResultsFound: webob.exc.HTTPInternalServerError
             }


entity_contorller = EntityReuest()


@singleton.singleton
class CdnResourceReuest(BaseContorller):

    CREATRESCHEMA = {
        'type': 'object',
        'required': ['name', 'etype', 'entity'],
        'properties': {
            'entity': {'type': 'integer',  'minimum': 1,
                       'description': '引用的域名实体id'},
            'etype': {'type': 'string',
                      "pattern": "^[a-z0-9][a-z0-9_-]+?[a-z0-9]+?$",
                      'description': '资源类型'},
            'name': {'type': 'string',
                     "pattern": "^[a-z0-9][a-z0-9_-]+?[a-z0-9]+?$",
                     'description': '资源名称'},
            'impl': {'type': 'string'},
            'auth': {'type': 'object'},
            'desc': {'type': 'string'},
        }
    }

    ASYNCSCHEMA = {
        'type': 'object',
        'required': ['version'],
        'properties': {
            'version': {'type': 'string', 'description': '资源版本号'},
            'impl': {'type': 'string'},
            'detail': {'oneOf': [{'type': 'object'},
                                 {'type': 'string'},
                                 {'type': 'null'}],
                       'description': 'detail of request'},
        }
    }

    LOGSCHEMA = {
        'type': 'object',
        'required': ['start', 'end', 'size_change', 'logfile', 'detail'],
        'properties':
            {
                'start': {'type': 'integer'},
                'end': {'type': 'integer'},
                'size_change': {'type': 'integer'},
                'logfile': {'type': 'string'},
                'detail': {'oneOf': [{'type': 'object'},
                                     {'type': 'string'},
                                     {'type': 'null'}],
                           'description': 'detail of request'},
            }
    }

    UPLOADSCHEMA = {
        'type': 'object',
        'required': ['fileinfo'],
        'properties': {
            'impl': {'type': 'string'},
            'auth': {'oneOf': [{'type': 'object'}, {'type': 'null'}]},
            'timeout': {'type': 'integer', 'minimum': 30, 'mixmum': 3600},
            'notify': {'oneOf': [{'type': 'object'}, {'type': 'null'}]},
            'fileinfo': common.FILEINFOSCHEMA,
        }
    }

    def _async_action(self, method, resource_id, body=None):
        caller = inspect.stack()[1][3]
        resource_id = int(resource_id)
        body = body or {}
        jsonutils.schema_validate(body, self.ASYNCSCHEMA)
        version = body.pop('version')
        detail = body.pop('detail', None)
        impl = body.pop('impl', None)
        asyncrequest = self.create_asyncrequest(body)
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id).one()
        if cdnresource.status != common.ENABLE:
            raise InvalidArgument('Cdn resource is not enable')
        rpc_ctxt = {'agents': [cdnresource.agent_id]}
        rpc_method = method
        rpc_args = dict(entity=cdnresource.entity,
                        resource_id=resource_id,
                        impl=impl or cdnresource.impl,
                        auth=safe_loads(cdnresource.auth),
                        version=version, detail=detail)
        rpc_args.update(body)
        target = targetutils.target_endpoint(endpoint=common.CDN)

        def wapper():
            self.send_asyncrequest(asyncrequest, target,
                                   rpc_ctxt, rpc_method, rpc_args)

        threadpool.add_thread(safe_func_wrapper, wapper, LOG)

        return resultutils.results(result='%s %s.%d thread spawning' % (caller, method, resource_id),
                                   data=[asyncrequest.to_dict()])

    def _sync_action(self, method, entity, args, timeout=None):
        caller = inspect.stack()[1][3]
        rpc = get_client()
        session = endpoint_session(readonly=True)
        cdndomain = model_query(session, CdnDomain, filter=CdnDomain.entity == entity).one()
        metadata = self.agent_metadata(cdndomain.agent_id)
        if not metadata:
            raise InvalidArgument('Agent is offline')
        target = targetutils.target_agent_by_string(manager_common.APPLICATION, metadata.get('host'))
        target.namespace = common.CDN
        if not timeout:
            finishtime, timeout = rpcfinishtime()
        else:
            finishtime = timeout + int(time.time()) - 1
        rpc_ret = rpc.call(target, ctxt={'finishtime': finishtime, 'agents': [cdndomain.agent_id, ]},
                           msg={'method': method, 'args': args},
                           timeout=timeout)
        if not rpc_ret:
            raise RpcResultError('%s result is None' % caller)
        if rpc_ret.get('resultcode') != manager_common.RESULT_SUCCESS:
            raise RpcResultError('%s fail %s' % (caller, rpc_ret.get('result')))
        return rpc_ret

    def index(self, req, body=None):
        body = body or {}
        order = body.pop('order', None)
        desc = body.pop('desc', False)
        page_num = int(body.pop('page_num', 0))
        session = endpoint_session(readonly=True)
        results = resultutils.bulk_results(session,
                                           model=CdnResource,
                                           columns=[CdnResource.resource_id,
                                                    CdnResource.name,
                                                    CdnResource.entity,
                                                    CdnResource.etype,
                                                    CdnResource.version,
                                                    CdnResource.status,
                                                    CdnResource.impl,
                                                    ],
                                           counter=CdnResource.entity,
                                           order=order, desc=desc,
                                           page_num=page_num)
        return results

    def create(self, req, body=None):
        body = body or {}
        jsonutils.schema_validate(body, self.CREATRESCHEMA)
        session = endpoint_session()

        entity = body.pop('entity')
        name = body.pop('name')
        etype = body.pop('etype')
        impl = body.get('impl', 'svn')
        auth = safe_dumps(body.get('auth'))
        desc = body.get('desc')
        # detail = body.get('detail')
        # data = dict(impl=impl)
        # if version:
        #     data.setdefault('version', version)
        # if auth:
        #     data.setdefault('auth', auth)
        # if detail:
        #     data.setdefault('detail', detail)
        with session.begin():

            if model_count_with_key(session, CdnResource,
                                    filter=and_(CdnResource.entity == entity,
                                                CdnResource.etype == etype,
                                                CdnResource.name == name)):
                raise InvalidArgument('Duplicat etype name %d' % entity)

            if not model_count_with_key(session, CdnDomain, filter=CdnDomain.entity == entity):
                raise InvalidArgument('Cdndomain  %d not exist' % entity)


            cdnresource = CdnResource(entity=entity,
                                      name=name,  etype=etype,
                                      impl=impl, auth=auth, desc=desc)
            session.add(cdnresource)
            session.flush()
        resource_id = cdnresource.resource_id
        try:
            self._sync_action(method='create_resource', entity=cdnresource.entity,
                              args=dict(entity=cdnresource.entity, resource_id=resource_id,
                                        name=name, etype=etype))
        except Exception:
            session.delete(cdnresource)
            raise
        return resultutils.results(result='create resource success', data=[dict(resource_id=cdnresource.resource_id,
                                                                                name=cdnresource.name,
                                                                                etype=cdnresource.etype,
                                                                                impl=cdnresource.impl,
                                                                                version=cdnresource.version,
                                                                                )])

    def show(self, req, resource_id, body=None):
        metadata = body.get('metadata', False)
        session = endpoint_session(readonly=True)
        query = session.query(CdnDomain.entity,
                              CdnDomain.internal,
                              CdnDomain.agent_id,
                              CdnDomain.port,
                              CdnDomain.character_set,
                              CdnResource.resource_id,
                              CdnResource.name,
                              CdnResource.etype,
                              CdnResource.version,
                              CdnResource.status,
                              CdnResource.impl,
                              CdnResource.desc,
                              ).join(CdnResource, and_(CdnDomain.entity == CdnResource.entity,
                                                       CdnResource.resource_id == resource_id))
        resource = query.one()
        domains = [domain.domain
                   for domain in model_query(session, Domain,
                                             filter=Domain.entity == resource.entity)]
        info = dict(entity=resource.entity,
                    internal=resource.internal,
                    agent_id=resource.agent_id,
                    port=resource.port,
                    character_set=resource.character_set,
                    domains=domains,
                    resource_id=resource.resource_id,
                    name=resource.name,
                    etype=resource.etype,
                    version=resource.version,
                    status=resource.status,
                    impl=resource.impl,
                    desc=resource.desc)
        if metadata:
            metadata = self.agent_metadata(resource.agent_id)
            info.setdefault('metadata', metadata)
        return resultutils.results(result='show cdn resource success', data=[info, ])

    def update(self, req, resource_id, body=None):
        """change status of cdn resource"""
        body = body or {}
        session = endpoint_session()
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id).one()
        if body.get('version'):
            cdnresource.version = body.get('version')
        if body.get('status'):
            if cdnresource.quotes:
                raise InvalidArgument('Change cdn resource status fail,still has quotes')
            cdnresource.status = body.get('status')
        session.flush()
        return resultutils.results(result='Update %s cdn resource success')

    def delete(self, req, resource_id):
        resource_id = int(resource_id)
        session = endpoint_session()
        query = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        query = query.options(joinedload(CdnResource.quotes, innerjoin=False))
        with session.begin():
            cdnresource = query.one()
            if cdnresource.status == common.ENABLE:
                raise InvalidArgument('Cdn resource is enable, can not delete')
            if cdnresource.quotes:
                raise InvalidArgument('Delete cdn resource fail,still has quotes')

            self._sync_action(method='delete_resource',
                              entity=cdnresource.entity, args=dict(entity=cdnresource.entity,
                                                                   resource_id=resource_id))
            query.delete()

        return resultutils.results(result='delete resource %d from %d success' % (resource_id, cdnresource.entity))

    def reset(self, req, resource_id, body=None):
        rpc_method = 'reset_resource'
        return self._async_action(method=rpc_method, resource_id=resource_id, body=body)

    def upgrade(self, req, resource_id, body=None):
        rpc_method = 'upgrade_resource'
        return self._async_action(method=rpc_method, resource_id=resource_id, body=body)

    def get_log(self, req, resource_id, body=None):
        body = body or {}
        desc = body.get('desc', True)
        limit = body.get('limit', 10)
        limit = min(limit, 30)
        session = endpoint_session(readonly=True)
        order = CheckOutLog.log_time
        if desc:
            order = order.desc()
        query = model_query(session, CheckOutLog,
                            filter=CheckOutLog.resource_id == resource_id).order(order).limit(limit)
        return resultutils.results(result='get cdn resource checkout log success',
                                   data=[dict(start=timeutils.unix_to_iso(log.start),
                                              end=timeutils.unix_to_iso(log.end),
                                              size_change=log.size_change,
                                              logfile=log.logfile,
                                              result=log.result,
                                              detail=safe_loads(log.detail),
                                              ) for log in query])

    def add_log(self, req, resource_id, body=None):
        """call by agent"""
        body = body or {}
        jsonutils.schema_validate(body, self.LOGSCHEMA)
        session = endpoint_session()
        checkoutlog = CheckOutLog(resource_id=resource_id,
                                  start=body.pop('start'), end=body.pop('end'),
                                  size_change=body.pop('size_change'), logfile=body.get('logfile'),
                                  result=body.get('result'),
                                  detail=safe_dumps(body.pop('detail')))
        session.add(checkoutlog)
        session.flush()
        return resultutils.results(result='add cdn resource checkout log success',
                                   data=[dict(log_time=checkoutlog.log_time)])

    def _shows(self, resource_ids, domains=False, metadatas=False):
        session = endpoint_session(readonly=True)
        query = session.query(CdnDomain.entity,
                              CdnDomain.internal,
                              CdnDomain.agent_id,
                              CdnDomain.port,
                              CdnResource.resource_id,
                              CdnResource.name,
                              CdnResource.etype,
                              CdnResource.version,
                              CdnResource.status,
                              CdnResource.impl,
                              ).join(CdnResource, and_(CdnDomain.entity == CdnResource.entity,
                                                       CdnResource.resource_id.in_(resource_ids)))
        resources = query.all()
        entitys = [resource.entity for resource in resources]
        threads = []
        if domains:
            domains = dict()

            def _domains():
                for domain in model_query(session, Domain,
                                          filter=Domain.entity.in_(entitys)):
                    try:
                        domains[domain.entity].append(domain.domain)
                    except KeyError:
                        domains[domain.entity] = [domain.domain]

            th = eventlet.spawn(_domains)
            threads.append(th)

        if metadatas:
            metadatas = dict()

            def _metadata():
                entitys_map = entity_contorller.shows(common.CDN, entitys=entitys, ports=False)
                for entity in entitys_map:
                    metadatas.setdefault(entity, entitys_map[entity]['metadata'])

            th = eventlet.spawn(_metadata)
            threads.append(th)

        for th in threads:
            th.wait()

        data = []
        for resource in resources:
            info = dict(entity=resource.entity,
                        resource_id=resource.resource_id,
                        agent_id=resource.agent_id,
                        port=resource.port,
                        name=resource.name,
                        etype=resource.etype,
                        version=resource.version,
                        status=resource.status,
                        impl=resource.impl)
            if metadatas:
                info.setdefault('metadata', metadatas.get(resource.entity))
            if domains:
                info.setdefault('domains', domains.get(resource.entity, []))
            data.append(info)
        session.close()
        return data

    def shows(self, req, resource_id, body=None):
        body = body or {}
        domains = body.get('domains', False)
        metadatas = body.get('metadata', False)
        resource_ids = argutils.map_to_int(resource_id)
        return resultutils.results(result='get cdn resources success',
                                   data=self._shows(resource_ids, domains, metadatas))

    def add_file(self, req, resource_id, body=None):
        body = body or {}
        resource_id = int(resource_id)
        jsonutils.schema_validate(body, self.UPLOADSCHEMA)
        timeout = body.pop('timeout', 300)
        impl = body.get('impl')
        auth = body.get('auth')
        notify = body.get('notify')
        if notify:
            for obj in six.itervalues(notify):
                jsonutils.schema_validate(obj, NOTIFYSCHEMA)
        fileinfo = body.pop('fileinfo')
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id).one_or_none()
        if not cdnresource:
            raise InvalidArgument('Cdn resource %d not exist' % resource_id)
        return self._sync_action(method='upload_resource_file', entity=cdnresource.entity,
                                 args=dict(entity=cdnresource.entity, resource_id=resource_id,
                                           impl=impl or cdnresource.impl,
                                           auth=auth or cdnresource.auth,
                                           uptimeout=timeout,
                                           notify=notify,
                                           fileinfo=fileinfo))

    def delete_file(self, req, resource_id, body=None):
        body = body or {}
        filename = body.pop('filename')
        if '..' in filename or os.sep in filename:
            raise InvalidArgument('filename error')
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        return self._sync_action(method='delete_resource_file', entity=cdnresource.entity,
                                 args=dict(entity=cdnresource.entity, resource_id=resource_id,
                                           filename=filename))

    def list_file(self, req, resource_id, body=None):
        body = body or {}
        deep = body.pop('deep', 1)
        path = body.get('path')
        if path and '..' in path:
            raise InvalidArgument('path error')
        deep = min(5, deep)
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        return self._sync_action(method='list_resource_file', entity=cdnresource.entity,
                                 args=dict(entity=cdnresource.entity, resource_id=resource_id,
                                           path=path, deep=deep))


@singleton.singleton
class CdnQuoteRequest(BaseContorller):
    def create(self, req, resource_id, body=None):
        body = body or {}
        desc = body.get('desc')
        resource_id = int(resource_id)
        quote = ResourceQuote(resource_id=resource_id, desc=desc)
        session = endpoint_session()
        session.add(quote)
        session.flush()
        return resultutils.results(result='quote cdn resource success',
                                   data=[dict(resource_id=resource_id, quote_id=quote.quote_id)])

    def delete(self, req, resource_id, quote_id, body=None):
        body = body or {}
        resource_id = int(resource_id)
        quote_id = int(quote_id)
        session = endpoint_session()
        query = model_query(session, ResourceQuote,
                            filter=and_(ResourceQuote.resource_id == resource_id,
                                        ResourceQuote.quote_id == quote_id))
        with session.begin():
            count = query.delete()
            if not count:
                raise InvalidArgument('Quote id not exist or not for resource')
            query.flush()
        return resultutils.results(result='delete cdn resource quote success',
                                   data=[dict(resource_id=resource_id, quote_id=quote_id)])
