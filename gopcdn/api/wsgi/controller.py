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
from simpleservice.ormdb.api import model_query
from simpleservice.rpc.exceptions import AMQPDestinationNotFound
from simpleservice.rpc.exceptions import MessagingTimeout
from simpleservice.rpc.exceptions import NoSuchMethod

from goperation import threadpool
from goperation.utils import safe_func_wrapper
from goperation.manager.utils import resultutils
from goperation.manager.utils import targetutils
from goperation.manager.utils import validateutils
from goperation.manager.api import get_session
from goperation.manager.exceptions import CacheStoneError
from goperation.manager.wsgi.entity.controller import EntityReuest
from goperation.manager.wsgi.endpoint.controller import EndpointReuest
from goperation.manager.wsgi.contorller import BaseContorller
from goperation.manager.wsgi.exceptions import RpcPrepareError
from goperation.manager.wsgi.exceptions import RpcResultError


from gopcdn import common
from gopcdn import utils
from gopcdn.api import endpoint_session
from gopcdn.models import PackageSource
from gopcdn.models import Package
from gopcdn.models import CdnResource
from gopcdn.models import CheckOutLog


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


@singleton.singleton
class CdnResourceReuest(BaseContorller):

    CREATRESCHEMA = {
        'type': 'object',
        'required': ['name', 'etype'],
        'properties': {
            'name': {'type': 'string'},
            'etype': [{'type': 'integer', 'minimum': 1, 'maxmum': 65535}, {'type': 'string'}],
            'version': {'type': 'string'},
            'cdnhost': {'type': 'object',
                        'required': ['hostname'],
                        'properties': {
                            'hostname': {'type': 'string'},
                            'listen': {'type': 'integer',  'minimum': 1, 'maxnum': 65534},
                            'charset': {'type': 'string'}}},
            'impl': {'type': 'string'},
            'uri': {'type': 'string'},
            'desc': {'type': 'string'},
            'auth': {'type': 'object'},
            'agent_id': {'type': 'integer',  'minimum': 1}
        }
    }

    LOGSCHEMA = {
        'type': 'object',
        'required': ['etype', 'impl', 'start', 'end', 'size_change', 'logfile', 'detail'],
        'properties':
            {
                'etype': [{'type': 'integer', 'minimum': 1, 'maxmum': 65535}, {'type': 'string'}],
                'impl': {'type': 'string'},
                'start': {'type': 'integer'},
                'end': {'type': 'integer'},
                'size_change': {'type': 'integer'},
                'logfile': {'type': 'string'},
                'detail': {'type': 'object'}
            }
    }

    def index(self, req, endpoint, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        order = body.pop('order', None)
        desc = body.pop('desc', False)
        page_num = int(body.pop('page_num', 0))
        session = endpoint_session(readonly=True)
        joins = joinedload(CdnResource.packages, innerjoin=False)
        results = resultutils.bulk_results(session,
                                           model=CdnResource,
                                           columns=[CdnResource.entity,
                                                    CdnResource.agent_id,
                                                    CdnResource.etype,
                                                    CdnResource.endpoint,
                                                    CdnResource.name,
                                                    CdnResource.version,
                                                    CdnResource.status,
                                                    CdnResource.packages],
                                           counter=CdnResource.entity,
                                           order=order, desc=desc,
                                           option=joins,
                                           filter=CdnResource.endpoint == endpoint,
                                           page_num=page_num)
        for column in results['data']:
            etype = common.EntityTypeMap[column.get('etype')]
            column['etype'] = etype
            packages = column.get('packages', [])
            column['packages'] = []
            for package in packages:
                column['packages'].append(dict(package_id=package.package_id,
                                               name=package.name,
                                               group=package.group))
        return results

    def create(self, req, endpoint, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        jsonutils.schema_validate(body, self.CREATRESCHEMA)
        session = endpoint_session()

        name = body.pop('name')
        etype = utils.validate_etype(body.pop('etype'))
        version = body.get('version')
        cdnhost = body.get('cdnhost')
        impl = body.get('impl', 'svn')
        uri = body.get('uri')
        auth = body.get('auth')
        agent_id = body.get('agent_id')
        desc = body.get('desc')
        detail = body.get('detail')

        endpoint_contorller = EndpointReuest()
        # find endpoint of CDN itself
        if not agent_id:
            for agent in endpoint_contorller.agents(req, common.CDN)['data']:
                agent_id = agent.get('agent_id')
                break
        # find endpoint resource for
        for result in endpoint_contorller.count(req, endpoint)['data']:
            if not result.get('count'):
                raise InvalidArgument('Endpoint %s not exist' % endpoint)

        data = dict(etype=etype,
                    impl=impl,
                    uri=uri,
                    auth=auth,
                    cdnhost=cdnhost,
                    version=version, detail=detail)
        entity_contorller = EntityReuest()
        result = entity_contorller.create(req, agent_id, common.CDN, data)
        session.add(CdnResource(entity=result['data'][0].get('entity'),
                                etype=etype, endpoint=endpoint, agent_id=agent_id,
                                name=name, version=version,
                                cdnhost=safe_dumps(cdnhost),
                                impl=impl, uri=uri, auth=safe_dumps(auth), desc=desc))
        session.flush()
        return result

    def show(self, req, endpoint, entity):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        entity_contorller = EntityReuest()
        agent = entity_contorller.show(req, common.CDN, int(entity))['data'][0]
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource,
                                  filter=and_(CdnResource.entity == entity,
                                              CdnResource.endpoint == endpoint)).\
            options(joinedload(CdnResource.packages, innerjoin=False).
                    joinedload(Package.sources, innerjoin=False)).one()
        data = [dict(endpoint=endpoint,
                     etype=common.EntityTypeMap[cdnresource.etype],
                     name=cdnresource.name,
                     version=cdnresource.version,
                     status=cdnresource.status,
                     agent=agent.get('agent_id'),
                     host=agent.get('host'),
                     desc=cdnresource.desc,
                     packages=[dict(package_id=package.package_id,
                                    group=package.group,
                                    mark=package.mark,
                                    version=package.version,
                                    desc=package.desc,
                                    magic=safe_loads(package.magic),
                                    sources=[dict(ptype=common.PackageTypeMap[source.ptype],
                                                  address=source.address,
                                                  desc=source.desc)
                                             for source in package.sources]
                                    ) for package in cdnresource.packages]
                     )]
        return resultutils.results(result='show cdn resource success', data=data)

    def update(self, req, endpoint, entity, body=None):
        """change status of cdn resource"""
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        session = endpoint_session()
        cdnresource = model_query(session, CdnResource, filter=CdnResource.entity == entity).one()
        if cdnresource.endpoint != endpoint:
            raise InvalidArgument('Update cdn resource find endpoint not match')
        if body.get('version'):
            cdnresource.version = body.get('version')
        if body.get('status'):
            if cdnresource.packages:
                raise InvalidArgument('Change cdn resource status fail,still has package use it')
            cdnresource.status = body.get('status')
        session.commit()
        return resultutils.results(result='Update %s cdn resource success')

    def delete(self, req, endpoint, entity):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        session = endpoint_session()
        cdnresource = model_query(session, CdnResource,
                                  filter=CdnResource.entity == entity).options(joinedload(CdnResource.packages,
                                                                                          innerjoin=False)).one()
        if cdnresource.endpoint != endpoint:
            raise InvalidArgument('Update cdn resource find endpoint not match')
        if cdnresource.packages:
            raise InvalidArgument('Delete cdn resource fail,still has package use it')
        with session.begin():
            session.delete(cdnresource)
            entity_contorller = EntityReuest()
            return entity_contorller.delete(req, endpoint=common.CDN, entity=[entity, ])

    def checkout(self, req, endpoint, entity, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        new_version = body.pop('version')
        detail = body.pop('detail')
        clean = body.pop('clean', False)
        asyncrequest = self.create_asyncrequest(body)
        entity_contorller = EntityReuest()
        agent = entity_contorller.show(req, common.CDN, int(entity))['data'][0]
        session = endpoint_session(readonly=True)
        cdnresource = model_query(session, CdnResource, filter=CdnResource.entity == entity)
        if cdnresource.endpoint != endpoint:
            raise InvalidArgument('Cdn resource for %s, not for %s' % (cdnresource.endpoint, endpoint))
        if cdnresource.status != common.ENABLE:
            raise InvalidArgument('Cdn resource is not enable')
        rpc_ctxt = {'agents': [agent.get('agent_id'), ]}
        rpc_method = 'checkout_resource'
        rpc_args = dict(entity=entity,
                        impl=cdnresource.impl,
                        uri=cdnresource.uri,
                        auth=safe_loads(cdnresource.auth),
                        version=new_version, detail=detail, clean=clean)
        target = targetutils.target_endpoint(endpoint=common.CDN)

        def wapper():
            self.send_asyncrequest(asyncrequest, target,
                                   rpc_ctxt, rpc_method, rpc_args)

        threadpool.add_thread(safe_func_wrapper, wapper, LOG)

        return resultutils.results(result='Checkout %s cdn resource async request thread spawning',
                                   data=[asyncrequest.to_dict()])

    def get_log(self, req, endpoint, entity, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        desc = body.get('desc', True)
        limit = body.get('limit', 10)
        limit = min(limit, 30)
        session = endpoint_session(readonly=True)
        order = CheckOutLog.log_time
        if desc:
            order = order.desc()
        query = model_query(session, CheckOutLog, filter=CheckOutLog.entity == entity).order(order).limit(limit)
        return resultutils.results(result='get cdn resource checkout log success',
                                   data=[dict(etype=common.EntityTypeMap[log.etype],
                                              impl=log.impl,
                                              start=timeutils.unix_to_iso(log.start),
                                              end=timeutils.unix_to_iso(log.end),
                                              size_change=log.size_change,
                                              logfile=log.logfile,
                                              result=log.result,
                                              detail=safe_loads(log.detail),
                                              ) for log in query])

    def add_log(self, req, endpoint, entity, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        jsonutils.schema_validate(body, self.LOGSCHEMA)
        etype = utils.validate_etype(body.pop('etype'))
        session = endpoint_session()
        print 'wtf'
        checkoutlog = CheckOutLog(entity=entity, etype=etype, impl=body.pop('impl'),
                                  start=body.pop('start'), end=body.pop('end'),
                                  size_change=body.pop('size_change'), log_file=body.get('logfile'),
                                  result=body.get('result'),
                                  detail=safe_dumps(body.pop('detail')))
        session.add(checkoutlog)
        session.flush()
        return resultutils.results(result='add cdn resource checkout log success',
                                   data=[dict(log_time=checkoutlog.log_time)])


@singleton.singleton
class PackageReuest(BaseContorller):

    CREATRESCHEMA = {
        'type': 'object',
        'required': ['entity', 'name', 'group', 'version', 'mark'],
        'properties':
            {
                'entity': {'type': 'integer',  'minimum': 1},
                'name': {'type': 'string'},
                'group': {'type': 'integer',  'minimum': 0},
                'version': {'type': 'string'},
                'mark': {'type': 'string'},
                'magic': {'type': 'object'},
                'desc': {'type': 'string'},
                'sources': {'type': 'array', 'minItems': 1,
                            'items': {'type': 'object',
                                      'required': ['address', 'ptype'],
                                      'properties': {'desc': {'type': 'string'},
                                                     'address': {'type': 'string'},
                                                     'ptype': {'type': 'string'}}}}
            }
    }

    UPDATESCHEMA = {
        'type': 'object',
        'required': ['version'],
        'properties':
            {
                'version': {'type': 'string'},
                'mark': {'type': 'string'},
                'magic': {'type': 'object'},
                'desc': {'type': 'string'},
                'sources': {'type': 'array', 'minItems': 1,
                            'items': {'type': 'object',
                                      'required': ['address', 'ptype'],
                                      'properties': {'desc': {'type': 'string'},
                                                     'address': {'type': 'string'},
                                                     'ptype': {'type': 'string'}}}}
            }
    }

    SOURCESCHEMA = {
        'type': 'object',
        'required': ['sources'],
        'properties': {
            'sources': {'type': 'array', 'minItems': 1,
                        'items': {'type': 'object',
                                  'required': ['ptype', 'address'],
                                  'properties': {'ptype': {'type': 'string'},
                                                 'address': {'type': 'string'},
                                                 'desc': {'type': 'string'},
                                                 }}}
        }
    }

    def index(self, req, endpoint, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        order = body.pop('order', None)
        page_num = int(body.pop('page_num', 0))
        session = endpoint_session(readonly=True)
        joins = joinedload(Package.sources, Package.checkoutresource, innerjoin=False)
        results = resultutils.bulk_results(session,
                                           model=Package,
                                           columns=[Package.package_id,
                                                    Package.name,
                                                    Package.group,
                                                    Package.version,
                                                    Package.mark,
                                                    Package.status,
                                                    Package.magic,
                                                    Package.checkoutresource,
                                                    Package.sources,
                                                    Package.desc],
                                           counter=Package.package_id,
                                           order=order,
                                           option=joins,
                                           filter=Package.endpoint == endpoint,
                                           page_num=page_num)
        for column in results['data']:
            checkoutresource = column.get('checkoutresource')
            if endpoint != checkoutresource.endpoint:
                raise ValueError('')
            column['checkoutresource'] = dict(entity=checkoutresource.entity,
                                              etype=common.EntityTypeMap[checkoutresource.etype],
                                              name=checkoutresource.name)
            magic = column.get('magic')
            column['magic'] = safe_loads(magic)
            sources = column.get('sources', [])
            column['sources'] = []
            for source in sources:
                column['sources'].append(dict(ptype=common.PackageTypeMap[source.ptype],
                                              address=source.address))
        return results

    def create(self, req, endpoint, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        jsonutils.schema_validate(body, self.CREATRESCHEMA)
        entity = body.pop('entity')
        name = body.pop('name')
        group = body.pop('group')
        version = body.pop('version')
        mark = body.pop('mark')
        magic = body.get('magic')
        desc = body.get('desc')
        sources = body.get('sources', [])
        session = endpoint_session()
        with session.begin():
            cdnresource = model_query(session, CdnResource, filter=CdnResource.entity == entity).one()
            if cdnresource.endpoint != endpoint:
                raise InvalidArgument('Add new package fail, endpoint not the same as cdn resource')
            package = Package(entity=entity,
                              endpoint=endpoint,
                              name=name,
                              group=group,
                              version=version,
                              mark=mark,
                              magic=safe_dumps(magic), desc=desc)
            session.add(package)
            session.flush()
            for source in sources:
                ptype = common.InvertPackageTypeMap[source['ptype']]
                session.add(PackageSource(package_id=package.package_id,
                                          ptype=ptype,
                                          address=source.get('address'), desc=source.get('desc')))
                session.flush()
        return resultutils.results(result='Add new package success')

    def show(self, req, endpoint, package_id):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        session = endpoint_session(readonly=True)
        joins = joinedload(Package.sources, Package.checkoutresource, innerjoin=False)
        package = model_query(session, Package, filter=Package.package_id == package_id).options(joins).one()
        etype = common.EntityTypeMap[package.checkoutresource.etype]
        return resultutils.results('Show package success',
                                   data=[dict(package_id=package.package_id,
                                              endpoint=endpoint,
                                              name=package.name,
                                              group=package.group,
                                              version=package.version,
                                              mark=package.mark,
                                              status=package.status,
                                              magic=safe_loads(package.magic),
                                              sources=[dict(ptype=source.ptype,
                                                            address=source.address,
                                                            desc=source.desc,
                                                            ) for source in package.sources],
                                              desc=package.desc,
                                              checkoutresource=dict(entity=package.checkoutresource.entity,
                                                                    etype=etype,
                                                                    name=package.checkoutresource.name))])

    def update(self, req, endpoint, package_id, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        jsonutils.schema_validate(body, self.UPDATESCHEMA)
        magic = body.get('magic')
        sources = body.get('sources', [])
        session = endpoint_session()
        with session.begin():
            package = model_query(session, Package, filter=Package.package_id == package_id).one()
            package.version = body.pop('version')
            if body.get('desc'):
                package.desc = body.get('desc')
            if package.endpoint != endpoint:
                raise InvalidArgument('Update package fail, endpoint not the same')
            if magic:
                package.magic = package.magic.update(magic) if package.magic else magic
            for source in sources:
                ptype = common.InvertPackageTypeMap[source.get('ptype')]
                query = model_query(session, PackageSource,
                                    filter=and_(PackageSource.package_id == package_id,
                                                PackageSource.ptype == ptype))
                data = {'address': source.get('address')}
                if source.get('desc'):
                    data.setdefault('desc', source.get('desc'))
                query.update(data)
        return resultutils.results('Update package success')

    def delete(self, req, endpoint, package_id):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        session = endpoint_session()
        with session.begin():
            package = model_query(session, Package, filter=Package.package_id == package_id).one()
            if package.endpoint != endpoint:
                raise InvalidArgument('Delete package fail, endpoint not the same')
            if package.group:
                raise InvalidArgument('Pacakge can not be delete, used by group %d' % package.group)
            session.delete(package)
        return resultutils.results('Update package success')

    def add_source(self, req, endpoint, package_id, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        jsonutils.schema_validate(body, self.SOURCESCHEMA)
        session = endpoint_session()
        with session.begin():
            package = model_query(session, Package,
                                  filter=Package.package_id == package_id).one()
            if package.endpoint != endpoint:
                raise InvalidArgument('Delete package fail, endpoint not the same')
            for source in body.get('sources'):
                ptype = common.PackageTypeMap[source.get('ptype')]
                session.add(PackageSource(package_id=package_id,
                                          ptype=ptype,
                                          address=source.get('address'),
                                          desc=source.get('desc')))
                session.flush()
        return resultutils.results('Update package success')

    def delete_source(self, req, endpoint, package_id, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        try:
            ptype = common.EntityTypeMap[body.get('ptype')]
        except KeyError:
            raise InvalidArgument('Delete cdn package source fail, ptype error')
        session = endpoint_session()
        joins = joinedload(Package.sources)
        with session.begin():
            package = model_query(session, Package,
                                  filter=Package.package_id == package_id).options(joins).one()
            if package.endpoint != endpoint:
                raise InvalidArgument('Delete package source fail, endpoint not the same')
            for source in package.sources:
                if source.ptype == ptype:
                    session.delete(source)
                    return resultutils.results('Delete package source success')
        return resultutils.results('No package source match')

    def update_source(self, req, endpoint, package_id, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        try:
            address = body.pop('address')
            ptype = common.EntityTypeMap[body.get('ptype')]
        except KeyError:
            raise InvalidArgument('Update cdn package source fail, ptype or address error')
        session = endpoint_session()
        joins = joinedload(Package.sources)
        with session.begin():
            package = model_query(session, Package,
                                  filter=Package.package_id == package_id).options(joins).one()
            if package.endpoint != endpoint:
                raise InvalidArgument('Update package source fail, endpoint not the same')
            for source in package.sources:
                if source.ptype == ptype:
                    source.address = address
                    if body.get('desc'):
                        source.desc = body.get('desc')
                    return resultutils.results('Update package source success')
        return resultutils.results('No package source match')

    def group(self, req, endpoint, package_id, body=None):
        endpoint = validateutils.validate_endpoint(endpoint)
        if endpoint == common.CDN:
            raise InvalidArgument('Ednpoint error for cdn resource')
        body = body or {}
        try:
            group = body.pop('group')
        except KeyError:
            raise InvalidArgument('Update cdn package group fail, no group found')
        session = endpoint_session()
        with session.begin():
            package = model_query(session, Package,
                                  filter=Package.package_id == package_id).one()
            if package.endpoint != endpoint:
                raise InvalidArgument('Update package source fail, endpoint not the same')
            package.group = group
            return resultutils.results('Update package group success')
        return resultutils.results('No package source match')
