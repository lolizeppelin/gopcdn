from simpleservice.wsgi import router
from simpleservice.wsgi.middleware import controller_return_response

from gopcdn import common
from gopcdn.api.wsgi import controller


COLLECTION_ACTIONS = ['index', 'create']
MEMBER_ACTIONS = ['show', 'update', 'delete']


class Routers(router.RoutersBase):

    def append_routers(self, mapper, routers=None):
        resource_name = 'cdnresource'
        collection_name = resource_name + 's'

        _controller = controller_return_response(controller.CdnResourceReuest(), controller.FAULT_MAP)
        collection = mapper.collection(collection_name=collection_name,
                                       resource_name=resource_name,
                                       controller=_controller,
                                       path_prefix='/%s/{endpoint}/%s' % (common.CDN, collection_name),
                                       member_prefix='/{entity}',
                                       collection_actions=COLLECTION_ACTIONS,
                                       member_actions=MEMBER_ACTIONS)
        # checkout new version
        collection.member.link('checkout', method='POST')
        # checkout log
        collection.member.link('log', name='get_cdn_log', method='GET', action='get_log')
        self._add_resource(mapper, _controller,
                           path='/%s/%s/{entity}' % (common.CDN, collection_name),
                           post_action='add_log')

        resource_name = 'package'
        collection_name = resource_name + 's'

        collection = mapper.collection(collection_name=collection_name,
                                       resource_name=resource_name,
                                       controller=controller_return_response(controller.PackageReuest(),
                                                                             controller.FAULT_MAP),
                                       path_prefix='/%s/{endpoint}/%s' % (common.CDN, collection_name),
                                       member_prefix='/{package_id}',
                                       collection_actions=COLLECTION_ACTIONS,
                                       member_actions=MEMBER_ACTIONS)
        collection.member.link('source', name='add_package_source', method='POST', action='add_source')
        collection.member.link('source', name='del_package_source', method='DELETE', action='delete_source')
        collection.member.link('source', name='update_package_source', method='PUT', action='update_source')
        collection.member.link('cdngroup', method='PUT')
