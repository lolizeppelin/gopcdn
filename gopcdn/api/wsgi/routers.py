from simpleservice.wsgi import router
from simpleservice.wsgi.middleware import controller_return_response

from gopcdn import common
from gopcdn.api.wsgi import domain
from gopcdn.api.wsgi import resource


COLLECTION_ACTIONS = ['index', 'create']
MEMBER_ACTIONS = ['show', 'update', 'delete']


class Routers(router.RoutersBase):

    def append_routers(self, mapper, routers=None):

        # ---------------------cdndomain routes
        resource_name = 'cdndomain'
        collection_name = resource_name + 's'
        _controller = controller_return_response(domain.CdnDomainRequest(), domain.FAULT_MAP)
        collection = mapper.collection(collection_name=collection_name,
                                       resource_name=resource_name,
                                       controller=_controller,
                                       path_prefix='/%s' % common.CDN,
                                       member_prefix='/{entity}',
                                       collection_actions=COLLECTION_ACTIONS,
                                       member_actions=['show', 'delete'])
        # add domain name
        collection.member.link('domains', method='POST', name='add_domain', action='add')
        # remove domain name
        collection.member.link('domains', method='DELETE', name='remove_domain', action='remove')

        self._add_resource(mapper, _controller,
                           path='/%s/agent/{agent_id}' % common.CDN,
                           get_action='ports')

        self._add_resource(mapper, _controller,
                           path='/%s/entitys' % common.CDN,
                           get_action='entitys')

        self._add_resource(mapper, _controller,
                           path='/%s/domain' % common.CDN,
                           get_action='domain')

        # ---------------------cdnresource routes
        resource_name = 'cdnresource'
        collection_name = resource_name + 's'
        _controller = controller_return_response(resource.CdnResourceReuest(), resource.FAULT_MAP)
        collection = mapper.collection(collection_name=collection_name,
                                       resource_name=resource_name,
                                       controller=_controller,
                                       path_prefix='/%s' % common.CDN,
                                       member_prefix='/{resource_id}',
                                       collection_actions=COLLECTION_ACTIONS,
                                       member_actions=MEMBER_ACTIONS)
        # bluk get resource info with detail
        collection.member.link('shows', method='GET')
        # reset cdn resource
        collection.member.link('reset', method='POST')
        # upgrade cdn resource
        collection.member.link('upgrade', method='POST')
        # get cdn resource log
        collection.member.link('log', name='get_cdn_log', method='GET', action='get_log')
        # agent report cdn resource log
        collection.member.link('log', name='post_cdn_log', method='POST', action='add_log')
        # add cdn resource file
        collection.member.link('file', name='add_cdn_file', method='POST', action='add_file')
        # delete cdn resource file
        collection.member.link('file', name='delete_cdn_file', method='DELETE', action='delete_file')
        # list cdn resource file
        collection.member.link('file', name='list_cdn_file', method='GET', action='list_file')

        # add cdn resource file
        collection.member.link('remark', name='add_remark', method='POST', action='add_remark')
        # delete cdn resource file
        collection.member.link('remark', name='del_remark', method='DELETE', action='del_remark')
        # list cdn resource file
        collection.member.link('remark', name='list_remarks', method='GET', action='list_remarks')

        # add version
        collection.member.link('version', name='add_version', method='POST', action='add_version')
        # delete cdn resource file
        collection.member.link('version', name='del_version', method='DELETE', action='del_version')
        # list cdn resource file
        collection.member.link('version', name='list_versions', method='GET', action='list_versions')

        # remove cdn resource one base quote
        collection.member.link('quote', name='del_quote', method='DELETE', action='unquote')
        # add cdn resource one base quote
        collection.member.link('quote', name='add_quote', method='POST', action='quote')

        # ---------------------cdnresource quote routes
        resource_name = 'quote'
        collection_name = resource_name + 's'
        _controller = controller_return_response(resource.CdnQuoteRequest(), resource.FAULT_MAP)
        mapper.collection(collection_name=collection_name,
                          resource_name=resource_name,
                          controller=_controller,
                          path_prefix='/%s/resversions/{version_id}' % common.CDN,
                          member_prefix='/{quote_id}',
                          collection_actions=['create'],
                          member_actions=['delete', 'show', 'delete'])
