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
from simpleservice.ormdb.exceptions import DBDuplicateEntry
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
from goperation.manager.api import get_cache
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
from gopcdn.models import ResourceVersion
from gopcdn.models import ResourceQuote
from gopcdn.models import CdnResourceRemark


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
                'version': {'type': 'string'},
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
        query = session.query(CdnDomain.agent_id,
                              CdnResource.entity,
                              CdnResource.status,
                              CdnResource.impl,
                              CdnResource.auth,
                              ).join(CdnResource, and_(CdnDomain.entity == CdnResource.entity,
                                                       CdnResource.resource_id == resource_id))

        cdnresource = query.one()
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
            raise InvalidArgument('Target entity agent is offline')
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

    def list(self, resource_ids=None, name=None, etype=None,
             versions=False, domains=False, metadatas=False):
        session = endpoint_session(readonly=True)

        filters = [CdnDomain.entity == CdnResource.entity]
        if resource_ids:
            filters.append(CdnResource.resource_id.in_(resource_ids))
        if name:
            filters.append(CdnResource.name == name)
        if etype:
            filters.append(CdnResource.etype == etype)
        if len(filters) > 1:
            filters = and_(*filters)
        else:
            filters = filters[0]

        query = session.query(CdnDomain.entity,
                              CdnDomain.internal,
                              CdnDomain.agent_id,
                              CdnDomain.port,
                              CdnResource.resource_id,
                              CdnResource.name,
                              CdnResource.etype,
                              CdnResource.status,
                              CdnResource.impl,
                              ).join(CdnResource, filters)
        resources = query.all()
        entitys = [resource.entity for resource in resources]
        threads = []
        if domains:
            _domains = dict()

            def _domains_fun():
                for domain in model_query(session, Domain,
                                          filter=Domain.entity.in_(entitys)):
                    try:
                        _domains[domain.entity].append(domain.domain)
                    except KeyError:
                        _domains[domain.entity] = [domain.domain]

            th = eventlet.spawn(_domains_fun)
            threads.append(th)

        if versions:
            _versions = dict()

            def _versions_fun():
                for version in model_query(session, ResourceVersion,
                                           filter=ResourceVersion.resource_id.in_(resource_ids)):
                    try:
                        _versions[version.resource_id].append(dict(version_id=version.version_id,
                                                                   vtime=version.vtime,
                                                                   version=version.version))
                    except KeyError:
                        _versions[version.resource_id] = [dict(version_id=version.version_id,
                                                               vtime=version.vtime,
                                                               version=version.version,
                                                               )]

            th = eventlet.spawn(_versions_fun)
            threads.append(th)

        if metadatas:
            _metadatas = dict()

            def _metadata_fun():
                entitys_map = entity_contorller.shows(common.CDN, entitys=entitys, ports=False)
                for entity in entitys_map:
                    _metadatas.setdefault(entity, entitys_map[entity]['metadata'])

            th = eventlet.spawn(_metadata_fun)
            threads.append(th)

        for th in threads:
            th.wait()

        data = []
        for resource in resources:
            info = dict(entity=resource.entity,
                        internal=resource.internal,
                        agent_id=resource.agent_id,
                        port=resource.port,
                        resource_id=resource.resource_id,
                        name=resource.name,
                        etype=resource.etype,
                        status=resource.status,
                        impl=resource.impl)
            if versions:
                info.setdefault('versions', _versions.get(resource.resource_id, []))
            if metadatas:
                info.setdefault('metadata', _metadatas.get(resource.entity))
            if domains:
                info.setdefault('domains', _domains.get(resource.entity, []))
            data.append(info)
        session.close()
        return data

    def shows(self, req, resource_id, body=None):
        body = body or {}
        domains = body.get('domains', False)
        metadatas = body.get('metadatas', False)
        versions = body.get('versions', False)
        etype = body.get('etype')
        name = body.get('name')
        if resource_id == 'all':
            resource_ids = None
        else:
            resource_ids = argutils.map_to_int(resource_id)
        return resultutils.results(result='get cdn resources success',
                                   data=self.list(resource_ids, name, etype,
                                                  versions, domains, metadatas))

    def index(self, req, body=None):
        body = body or {}
        order = body.pop('order', None)
        desc = body.pop('desc', False)
        page_num = int(body.pop('page_num', 0))

        filters = []
        etype = body.get('etype')
        name = body.get('name')

        if etype:
            filters.append(CdnResource.etype == etype)
        if name:
            filters.append(CdnResource.name == name)

        session = endpoint_session(readonly=True)
        results = resultutils.bulk_results(session,
                                           model=CdnResource,
                                           columns=[CdnResource.resource_id,
                                                    CdnResource.name,
                                                    CdnResource.entity,
                                                    CdnResource.etype,
                                                    CdnResource.status,
                                                    CdnResource.quotes,
                                                    CdnResource.impl,
                                                    ],
                                           counter=CdnResource.entity,
                                           filter=and_(*filters) if filters else None,
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
        with session.begin():

            if model_count_with_key(session, CdnResource,
                                    filter=and_(CdnResource.entity == entity,
                                                CdnResource.etype == etype,
                                                CdnResource.name == name)):
                raise InvalidArgument('Duplicat etype name with %d' % entity)

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
            session.flush()
            raise
        return resultutils.results(result='create resource success', data=[dict(resource_id=cdnresource.resource_id,
                                                                                name=cdnresource.name,
                                                                                etype=cdnresource.etype,
                                                                                impl=cdnresource.impl
                                                                                )])

    def show(self, req, resource_id, body=None):
        body = body or {}
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
                              CdnResource.quotes,
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
                    status=resource.status,
                    impl=resource.impl,
                    quotes=resource.quotes,
                    desc=resource.desc)
        if metadata:
            metadata = self.agent_metadata(resource.agent_id)
            info.setdefault('metadata', metadata)
        return resultutils.results(result='show cdn resource success', data=[info, ])

    def update(self, req, resource_id, body=None):
        """change status of cdn resource"""
        body = body or {}
        resource_id = int(resource_id)
        session = endpoint_session()
        cdnresource = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id).one()
        if body.get('status'):
            cdnresource.status = body.get('status')
        session.flush()
        cache = get_cache()
        pipe = cache.pipeline()
        pipe.zadd(common.CACHESETNAME, int(time.time()), str(resource_id))
        pipe.expire(common.CACHESETNAME, common.CACHETIME)
        pipe.execute()
        return resultutils.results(result='Update %s cdn resource success')

    def delete(self, req, resource_id, body=None):
        resource_id = int(resource_id)
        session = endpoint_session()
        query = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        query = query.options(joinedload(CdnResource.versions, innerjoin=False))
        with session.begin():
            cdnresource = query.one()
            if cdnresource.status == common.ENABLE:
                raise InvalidArgument('Cdn resource is enable, can not delete')
            if cdnresource.versions:
                raise InvalidArgument('Delete cdn resource fail,still has versions')
            if cdnresource.quotes:
                raise InvalidArgument('Delete cdn resource base quote is not 0')
            self._sync_action(method='delete_resource',
                              entity=cdnresource.entity, args=dict(entity=cdnresource.entity,
                                                                   resource_id=resource_id))
            query.delete()
        cache = get_cache()
        pipe = cache.pipeline()
        pipe.zadd(common.CACHESETNAME, int(time.time()), str(resource_id))
        pipe.expire(common.CACHESETNAME, common.CACHETIME)
        pipe.execute()
        return resultutils.results(result='delete resource %d from %d success' % (resource_id, cdnresource.entity))

    def reset(self, req, resource_id, body=None):
        rpc_method = 'reset_resource'
        return self._async_action(method=rpc_method, resource_id=resource_id, body=body)

    def upgrade(self, req, resource_id, body=None):
        rpc_method = 'upgrade_resource'
        return self._async_action(method=rpc_method, resource_id=resource_id, body=body)

    def get_log(self, req, resource_id, body=None):
        body = body or {}
        version = body.get('version')
        desc = body.get('desc', True)
        limit = body.get('limit', 10)
        limit = min(limit, 30)
        session = endpoint_session(readonly=True)
        order = CheckOutLog.start
        if desc:
            order = order.desc()
        _filter = CheckOutLog.resource_id == resource_id
        if version:
            _filter = and_(_filter, CheckOutLog.version == version)
        query = model_query(session, CheckOutLog,
                            filter=_filter).order_by(order).limit(limit)
        return resultutils.results(result='get cdn resource checkout log success',
                                   data=[dict(start=timeutils.unix_to_iso(log.start),
                                              end=timeutils.unix_to_iso(log.end),
                                              size_change=log.size_change,
                                              logfile=log.logfile,
                                              version=log.version,
                                              result=log.result,
                                              detail=safe_loads(log.detail),
                                              ) for log in query])

    def add_log(self, req, resource_id, body=None):
        """call by agent"""
        body = body or {}
        jsonutils.schema_validate(body, self.LOGSCHEMA)
        session = endpoint_session()
        checkoutlog = CheckOutLog(resource_id=resource_id,
                                  version=body.pop('version'),
                                  start=body.pop('start'), end=body.pop('end'),
                                  size_change=body.pop('size_change'), logfile=body.get('logfile'),
                                  result=body.get('result'),
                                  detail=safe_dumps(body.pop('detail')))
        session.add(checkoutlog)
        session.flush()
        return resultutils.results(result='add cdn resource checkout log success',
                                   data=[dict(log_time=checkoutlog.log_time)])

    def add_remark(self, req, resource_id, body=None):
        body = body or {}
        if 'username' not in body:
            raise InvalidArgument('username not found')
        if 'message' not in body:
            raise InvalidArgument('message not found')
        resource_id = int(resource_id)
        session = endpoint_session()
        remark = CdnResourceRemark(resource_id=resource_id,
                                   rtime=int(time.time()),
                                   username=str(body.get('username')),
                                   message=str(body.get('message')),
                                   )
        session.add(remark)
        session.flush()
        return resultutils.results(result='Add remark success')

    def del_remark(self, req, resource_id, body=None):
        body = body or {}
        remark_id = int(body.pop('remark_id'))
        session = endpoint_session()
        query = model_query(session, CdnResourceRemark, filter=CdnResourceRemark.remark_id == remark_id)
        query.delete()
        return resultutils.results(result='Delete remark success')

    def list_remarks(self, req, resource_id, body=None):
        body = body or {}
        page_num = int(body.pop('page_num', 0))
        session = endpoint_session(readonly=True)
        results = resultutils.bulk_results(session,
                                           model=CdnResourceRemark,
                                           columns=[CdnResourceRemark.rtime,
                                                    CdnResourceRemark.username,
                                                    CdnResourceRemark.message,
                                                    ],
                                           counter=CdnResourceRemark.remark_id,
                                           filter=CdnResourceRemark.resource_id == resource_id,
                                           order=CdnResourceRemark.rtime,
                                           desc=True,
                                           page_num=page_num,
                                           limit=10,
                                           )
        return results

    def add_version(self, req, resource_id, body=None):
        body = body or {}
        version = body.get('version')
        resource_id = int(resource_id)
        session = endpoint_session()
        resourceversion = ResourceVersion(resource_id=resource_id,
                                          vtime=int(time.time()),
                                          version=version,
                                          desc=body.get('desc'))
        session.add(resourceversion)
        try:
            session.flush()
        except DBDuplicateEntry:
            LOG.warning('Duplicate resource version %s add for %d' % (version, resource_id))
            session.merge(resourceversion)
            session.flush()

        def _notify():
            cache = get_cache()
            pipe = cache.pipeline()
            pipe.zadd(common.CACHESETNAME, int(time.time()), str(resource_id))
            pipe.expire(common.CACHESETNAME, common.CACHETIME)
            pipe.execute()

        eventlet.spawn_n(_notify)
        return resultutils.results(result='Add version for resource success',
                                   data=[dict(version_id=resourceversion.version_id,
                                              version=version,
                                              resource_id=resource_id,
                                              )])

    def delete_version(self, req, resource_id, body=None):
        body = body or {}
        version = body.get('version')
        resource_id = int(resource_id)
        session = endpoint_session()
        query = model_query(session, ResourceVersion,
                            filter=and_(ResourceVersion.resource_id == resource_id,
                                        ResourceVersion.version == version))
        resourceversion = query.one()
        with session.begin():
            cdnresource = resourceversion.cdnresource
            self._sync_action(method='delete_resource_version',
                              entity=cdnresource.entity, args=dict(entity=cdnresource.entity,
                                                                   resource_id=resource_id,
                                                                   version=version))
            query.delete()
        cache = get_cache()
        pipe = cache.pipeline()
        pipe.zadd(common.CACHESETNAME, int(time.time()), str(resource_id))
        pipe.expire(common.CACHESETNAME, common.CACHETIME)
        pipe.execute()
        return resultutils.results(result='Delete version for resource success')

    def list_versions(self, req, resource_id, body=None):
        body = body or {}
        quotes = body.get('quotes', False)
        desc = body.get('desc', True)
        resource_id = int(resource_id)
        session = endpoint_session(readonly=True)
        query = model_query(session, ResourceVersion,
                            filter=ResourceVersion.resource_id == resource_id)
        if quotes:
            query = query.options(joinedload(ResourceVersion.quotes))

        data = []
        for version in query:
            v = dict(version_id=version.version_id,
                     version=version.version,
                     vtime=version.vtime,
                     resource_id=resource_id)
            if desc:
                v.setdefault('desc', version.desc)
            if quotes:
                v.setdefault('quotes', [dict(quote_id=quote.quote_id, desc=quote.desc)
                                        if desc else dict(quote_id=quote.quote_id)
                                        for quote in version.quotes])
            data.append(v)

        return resultutils.results(result='list version for resource success',
                                   data=data)

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

    def quote(self, req, resource_id, body=None):
        resource_id = int(resource_id)
        session = endpoint_session()
        query = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        with session.begin():
            cdnresource = query.one()
            if cdnresource.status != common.ENABLE:
                raise InvalidArgument('Cdn resource is not enable, can add quote')
            cdnresource.quotes = cdnresource.quotes + 1
            session.flush()
        return resultutils.results(result='cdn resources add one quote success',
                                   data=[dict(resource_id=cdnresource.resource_id,
                                              name=cdnresource.name,
                                              etype=cdnresource.etype,
                                              quotes=cdnresource.quotes,
                                              )])

    def unquote(self, req, resource_id, body=None):
        resource_id = int(resource_id)
        session = endpoint_session()
        query = model_query(session, CdnResource, filter=CdnResource.resource_id == resource_id)
        with session.begin():
            cdnresource = query.one()
            if cdnresource.quotes:
                cdnresource.quotes = cdnresource.quotes - 1
                session.flush()
        return resultutils.results(result='cdn resources remove one quote success',
                                   data=[dict(resource_id=cdnresource.resource_id,
                                              name=cdnresource.name,
                                              etype=cdnresource.etype,
                                              quotes=cdnresource.quotes,
                                              )])

    def vquote(self, req, resource_id, body=None):
        body = body or {}
        resource_id = int(resource_id)
        version = body.get('version')
        desc = body.get('desc')
        session = endpoint_session()
        query = session.query(CdnResource.resource_id,
                              CdnResource.name,
                              CdnResource.etype,
                              CdnResource.status,
                              ResourceVersion.version_id,
                              ResourceVersion.version,
                              ).join(ResourceVersion,
                                     and_(CdnResource.resource_id == ResourceVersion.resource_id,
                                          ResourceVersion.version == version))
        query = query.filter(CdnResource.resource_id == resource_id)
        with session.begin():
            cdnresource = query.one_or_none()
            if not cdnresource:
                raise InvalidArgument('Can not found cdn resouce version %s' % version)
            if cdnresource.status != common.ENABLE:
                raise InvalidArgument('Cdn resource is not enable, can add version quote')
            version_id = cdnresource.version_id
            vquote = ResourceQuote(version_id=version_id, desc=desc)
            session.add(vquote)
            session.flush()
        return resultutils.results(result='cdn resources add version quote success',
                                   data=[dict(resource_id=cdnresource.resource_id,
                                              name=cdnresource.name,
                                              etype=cdnresource.etype,
                                              version_id=version_id,
                                              version=version,
                                              quote_id=vquote.quote_id)])


@singleton.singleton
class CdnQuoteRequest(BaseContorller):
    def create(self, req, body=None):
        body = body or {}
        version_id = int(body.pop('version_id'))
        desc = body.get('desc')
        quote = ResourceQuote(version_id=version_id, desc=desc)
        session = endpoint_session()
        session.add(quote)
        session.flush()
        return resultutils.results(result='quote cdn resource success',
                                   data=[dict(version_id=version_id, quote_id=quote.quote_id)])

    def show(self, req, quote_id, body=None):
        body = body or {}
        quote_id = int(quote_id)
        session = endpoint_session()
        query = model_query(session, ResourceQuote,
                            filter=ResourceQuote.quote_id == quote_id)
        quote = query.one()
        cdnresourceversion = quote.cdnresourceversion
        return resultutils.results(result='delete cdn resource quote success',
                                   data=[dict(quote_id=quote.quote_id,
                                              version=dict(version_id=cdnresourceversion.version_id,
                                                           version=cdnresourceversion.version,
                                                           resource_id=cdnresourceversion.resource_id,
                                                           desc=cdnresourceversion.desc),
                                              desc=quote.desc)])

    def update(self, req, quote_id, body=None):
        body = body or {}
        if 'version' not in body:
            raise InvalidArgument('Need version')
        version = body.get('version')
        quote_id = int(quote_id)
        session = endpoint_session()

        query = model_query(session, ResourceQuote, filter=ResourceQuote.quote_id == quote_id)
        quote = query.one()

        with session.begin():
            old = quote.cdnresourceversion
            new = model_query(session, ResourceVersion,
                              filter=and_(ResourceVersion.resource_id == old.resource_id,
                                          ResourceVersion.version == version)).one_or_none()
            if not new:
                raise InvalidArgument('version can not be found in same resource %d' % old.resource_id)

            if quote.version_id != new.version_id:
                quote.version_id = new.version_id
                session.flush()

        return resultutils.results(result='delete cdn resource quote success',
                                   data=[dict(quote_id=quote.quote_id,
                                              version=dict(version_id=new.version_id,
                                                           version=new.version,
                                                           resource_id=new.resource_id,
                                                           desc=new.desc),
                                              desc=quote.desc)])

    def delete(self, req, quote_id, body=None):
        body = body or {}
        quote_id = int(quote_id)
        session = endpoint_session()
        query = model_query(session, ResourceQuote,
                            filter=ResourceQuote.quote_id == quote_id)
        quote = query.one_or_none()
        if not quote:
            LOG.warning('Quote id not found, but return success' % quote_id)
            return resultutils.results(result='no quote found')
        version_id = quote.version_id
        with session.begin():
            count = query.delete()
            if not count:
                LOG.warning('Quote id not exist or not for any resource')
            query.flush()
        return resultutils.results(result='delete cdn resource quote success',
                                   data=[dict(quote_id=quote_id, version_id=version_id)])
