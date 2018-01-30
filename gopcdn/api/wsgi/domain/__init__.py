# -*- coding:utf-8 -*-
import webob.exc

from sqlalchemy.sql import and_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from simpleutil.common.exceptions import InvalidArgument
from simpleutil.log import log as logging
from simpleutil.utils import jsonutils
from simpleutil.utils import singleton
from simpleutil.utils import argutils
from simpleservice.ormdb.api import model_query
from simpleservice.ormdb.api import model_count_with_key
from simpleservice.rpc.exceptions import AMQPDestinationNotFound
from simpleservice.rpc.exceptions import MessagingTimeout
from simpleservice.rpc.exceptions import NoSuchMethod

from goperation.manager import common as manager_common
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
class CdnDomainRequest(BaseContorller):


    CREATRESCHEMA = {
        'type': 'object',
        'required': ['agent_id'],
        'properties': {
            'internal': {'type': 'boolean', 'description': '对内CDN,在没有域名情况下使用local_ip'},
            'agent_id': {'type': 'integer',  'minimum': 1},
            'domains': common.DOMAINS,
            'ipaddr': {'type': 'string', 'format': 'ipv4',
                       'description': '指定外网IP, 否则使用全局IP'},
            'port':  {'type': 'integer',  'minimum': 1, 'maxmum': 65534},
            'character_set': {'type': 'string'},
        }
    }

    def index(self, req, body=None):
        body = body or {}
        order = body.pop('order', None)
        desc = body.pop('desc', False)
        page_num = int(body.pop('page_num', 0))
        session = endpoint_session(readonly=True)
        joins = joinedload(CdnDomain.domains, innerjoin=False)
        results = resultutils.bulk_results(session,
                                           model=CdnDomain,
                                           columns=[CdnDomain.entity,
                                                    CdnDomain.internal,
                                                    CdnDomain.agent_id,
                                                    CdnDomain.port,
                                                    CdnDomain.character_set,
                                                    CdnDomain.domains
                                                    ],
                                           counter=CdnDomain.entity,
                                           order=order, desc=desc,
                                           option=joins,
                                           page_num=page_num)
        for column in results['data']:
            domains = column.get('domains', [])
            column['domains'] = []
            for domain in domains:
                column['domains'].append(domain.domain)
        return results

    def create(self, req, body=None):
        """
        生成域名组, 域名组下可以有多个域名
        域名组下没有域名的时, nginx的servername不会填写域名
        web服务器端口必须在管理端口范围外
        """
        body = body or {}
        jsonutils.schema_validate(body, self.CREATRESCHEMA)
        internal = body.get('internal', False)
        agent_id = body.pop('agent_id')
        ipaddr = body.get('ipaddr')
        port = body.get('port', 80)
        domains = body.get('domains')
        character_set = body.get('character_set', 'utf8')
        metadata = self.agent_metadata(agent_id)
        if not metadata:
            raise InvalidArgument('Agent not online not not exist')
        if ipaddr:
            if ipaddr not in metadata.get('external_ips'):
                raise InvalidArgument('%s not on agent %d' % (ipaddr, agent_id))
        session = endpoint_session()
        with session.begin():
            if not domains:
                # 避免无hostname的域名实体使用相同的port
                query = model_query(session, CdnDomain, filter=and_(CdnDomain.agent_id == agent_id,
                                                                    CdnDomain.port == port))
                query = query.options(joinedload(CdnDomain.domains, innerjoin=False))
                for _cdndomain in query:
                    if not _cdndomain.domains:
                        raise InvalidArgument('No hostname domain in same port and agent')
            else:
                # 相同hostname检测
                if model_count_with_key(session, Domain, Domain.domain.in_(domains)):
                    raise InvalidArgument('Domain hostname Dulupe')
            result = entity_contorller.create(req, agent_id, common.CDN, body)
            entity = result['data'][0].get('entity')
            cdndomain = CdnDomain(entity=entity, internal=internal,
                                  agent_id=agent_id, port=port,
                                  character_set=character_set)
            session.add(cdndomain)
            if domains:
                for domain in domains:
                    session.add(Domain(domain=domain, entity=cdndomain.entity))
                    session.flush()
        return resultutils.results(result='Create cdn domain success', data=[dict(entity=cdndomain.entity,
                                                                                  internal=cdndomain.internal,
                                                                                  agent_id=cdndomain.agent_id,
                                                                                  metadata=metadata,
                                                                                  port=port,
                                                                                  domains=domains,
                                                                                  character_set=character_set,
                                                                                  )])

    def show(self, req, entity, body=None):
        body = body or {}
        resources = body.get('resources', False)
        session = endpoint_session(readonly=True)
        query = model_query(session, CdnDomain, filter=CdnDomain.entity == entity)
        query = query.options(joinedload(CdnDomain.domains, innerjoin=False))
        cdndomain = query.one()
        metadata = self.agent_metadata(cdndomain.agent_id)
        info = dict(entity=cdndomain.entity,
                    agent_id=cdndomain.agent_id,
                    metadata=metadata,
                    internal=cdndomain.internal,
                    port=cdndomain.port,
                    character_set=cdndomain.character_set,
                    domains=[domain.domain for domain in cdndomain.domains])
        if resources:
            info.setdefault('resources', [dict(resource_id=cdnresource.resource_id,
                                               name=cdnresource.name,
                                               etype=cdnresource.etype,
                                               status=cdnresource.status,
                                               impl=cdnresource.impl,
                                               ) for cdnresource in cdndomain.resources])

        return resultutils.results(result='Show cdn domain success',
                                   data=[info, ])

    def delete(self, req, entity, body=None):
        body = body or {}
        session = endpoint_session()
        query = model_query(session, CdnDomain, filter=CdnDomain.entity == entity)
        query = query.options(joinedload(CdnDomain.resources, innerjoin=False))
        with session.begin():
            cdndomain = query.one()
            if cdndomain.resources:
                raise InvalidArgument('Domain entity has resources')
            LOG.info('Try delete domain entity %d' % cdndomain.entity)
            for domain in cdndomain.domains:
                LOG.info('Remove hostname %s' % domain.domain)
            query.delete()
            return entity_contorller.delete(req, endpoint=common.CDN, entity=entity, body=body)

    def add(self, req, entity, body=None):
        """域名组中添加域名"""
        body = body or {}
        SCHEMA = {'type': 'object',
                  'required': ['domains'],
                  'properties': {'domains': common.DOMAINS}
                  }
        jsonutils.schema_validate(body, SCHEMA)
        session = endpoint_session()
        rpc = get_client()
        query = model_query(session, CdnDomain, filter=CdnDomain.entity == entity)
        query = query.options(joinedload(CdnDomain.domains, innerjoin=False))
        cdndomain = query.one()
        domains = set(body.get('domains')) - set([domain.domain for domain in cdndomain.domains])
        if not domains:
            return resultutils.results(result='No domain name need add')
        metadata = self.agent_metadata(cdndomain.agent_id)
        target = targetutils.target_agent_by_string(manager_common.APPLICATION,
                                                    metadata.get('host'))
        target.namespace = common.CDN
        with session.begin():
            for domain in domains:
                session.add(Domain(entity=entity, domain=domain))
                session.flush()
            finishtime, timeout = rpcfinishtime()
            rpc_ret = rpc.call(target, ctxt={'finishtime': finishtime, 'agents': [cdndomain.agent_id, ]},
                               msg={'method': 'add_hostnames', 'args': dict(entity=entity,
                                                                            metadata=metadata,
                                                                            domains=domains)},
                               timeout=timeout)
            if not rpc_ret:
                raise RpcResultError('add new domain name result is None')
            if rpc_ret.get('resultcode') != manager_common.RESULT_SUCCESS:
                raise RpcResultError('add new domain name fail %s' % rpc_ret.get('result'))
        return resultutils.results(result='add new domain name success')

    def remove(self, req, entity, body=None):
        """移除域名组中的域名"""
        body = body or {}
        SCHEMA = {'type': 'object',
                  'required': ['domains'],
                  'properties': {'domains': common.DOMAINS}
                  }
        jsonutils.schema_validate(body, SCHEMA)
        session = endpoint_session()
        rpc = get_client()
        query = model_query(session, CdnDomain, filter=CdnDomain.entity == entity)
        query = query.options(joinedload(CdnDomain.domains, innerjoin=False))
        cdndomain = query.one()
        domains = set(body.get('domains'))
        before = set([domain.domain for domain in cdndomain.domains])
        if domains - before:
            raise InvalidArgument('Some domain name not in CdnDomain %d' % CdnDomain.entity)
        after = before - domains
        if not after:
            # 避免删除后, 无hostname的域名实体使用相同的port
            query = model_query(session, CdnDomain,
                                filter=and_(CdnDomain.agent_id == cdndomain.agent_id,
                                             CdnDomain.port == cdndomain.port))
            query = query.options(joinedload(CdnDomain.domains, innerjoin=False))
            for _cdndomain in query:
                if not _cdndomain.domains:
                    raise InvalidArgument('No hostname domain in same port and agent')
        metadata = self.agent_metadata(cdndomain.agent_id)
        target = targetutils.target_agent_by_string(manager_common.APPLICATION,
                                                    metadata.get('host'))
        target.namespace = common.CDN
        with session.begin():
            for domain in cdndomain.domains:
                if domain.domain in domains:
                    session.delete(domain)
                    session.flush()
            finishtime, timeout = rpcfinishtime()
            rpc_ret = rpc.call(target, ctxt={'finishtime': finishtime, 'agents': [cdndomain.agent_id, ]},
                               msg={'method': 'remove_hostnames', 'args': dict(entity=entity,
                                                                               metadata=metadata,
                                                                               domains=list(domains))},
                               timeout=timeout)
            if not rpc_ret:
                raise RpcResultError('add new domain name result is None')
            if rpc_ret.get('resultcode') != manager_common.RESULT_SUCCESS:
                raise RpcResultError('remove new domain name fail %s' % rpc_ret.get('result'))
        return resultutils.results(result='remove new domain name success')

    def domain(self, req, body=None):
        """search domain by name"""
        body = body or {}
        SCHEMA = {'type': 'object',
                  'required': ['domain'],
                  'properties': {'domain': common.DOMAIN,
                                 'metadata':  {'type': 'boolean'}},
                  }
        jsonutils.schema_validate(body, SCHEMA)
        domain = body.pop('domain')
        metadata = body.get('metadata', False)
        session = endpoint_session(readonly=True)
        query = session.query(CdnDomain).join(Domain,
                                              and_(CdnDomain.entity == Domain.entity,
                                                   Domain.domain == domain))
        cdndomain = query.one()

        info = dict(entity=cdndomain.entity,
                    agent_id=cdndomain.agent_id,
                    port=cdndomain.port,
                    internal=cdndomain.internal,
                    character_set=cdndomain.character_set)
        if metadata:
            metadata = self.agent_metadata(cdndomain.agent_id)
            info.setdefault('metadata', metadata)

        return resultutils.results(result='find domian entity success',
                                   data=[info, ])

    def entitys(self, req, body=None):
        body = body or {}
        entitys = body.get('entitys')
        if not entitys:
            return resultutils.results(result='not any domain entitys found')
        entitys = argutils.map_to_int(entitys)
        session = endpoint_session(readonly=True)
        maps = dict()
        for domain in model_query(session, Domain, filter=Domain.entity.in_(entitys)):
            try:
                maps[domain.entity].append(domain.domain)
            except KeyError:
                maps[domain.entity] = [domain.domain]
        query = model_query(session, CdnDomain, filter=CdnDomain.entity.in_(entitys))
        query = query.options(joinedload(CdnDomain.resources, innerjoin=False))
        return resultutils.results(result='list domain entity domain names success',
                                   data=[dict(entity=cdndomain.entity,
                                              internal=cdndomain.internal,
                                              port=cdndomain.port,
                                              character_set=cdndomain.character_set,
                                              domains=maps[cdndomain.entity] if cdndomain.entity in maps else [],
                                              resources=[dict(resource_id=cdnresource.resource_id,
                                                              name=cdnresource.name,
                                                              etype=cdnresource.etype,
                                                              # version=cdnresource.version,
                                                              status=cdnresource.status,
                                                              impl=cdnresource.impl)
                                                         for cdnresource in cdndomain.resources]
                                              )
                                         for cdndomain in query])

    def ports(self, req, agent_id, body=None):
        """获取gopcdn 所支持的端口列表"""
        rpc = get_client()
        agent_id = int(agent_id)
        metadata = self.agent_metadata(agent_id)
        if not metadata:
            raise InvalidArgument('Agent not online not not exist')
        target = targetutils.target_agent_by_string(manager_common.APPLICATION,
                                                    metadata.get('host'))
        target.namespace = common.CDN
        finishtime, timeout = rpcfinishtime()
        rpc_ret = rpc.call(target, ctxt={'finishtime': finishtime, 'agents': [agent_id]},
                           msg={'method': 'deploer_ports'},
                           timeout=timeout)
        if not rpc_ret:
            raise RpcResultError('get gpocdn deploer ports result is None')
        return resultutils.results(result='get gpocdn deploer ports success',
                                   data=rpc_ret.get('ports'))