# -*- coding:utf-8 -*-
import time
import simpleservice

from simpleutil.config import cfg
from goperation import config

from goperation.api.client import ManagerClient

from gopcdn.api.client import GopCdnClient
from gopcdn import common


a = 'C:\\Users\\loliz_000\\Desktop\\etc\\goperation\\goperation.conf'
b = 'C:\\Users\\loliz_000\\Desktop\\etc\\goperation\\gcenter.conf'
config.configure('test', [a, b])

# wsgi_url = '127.0.0.1'
wsgi_url = '172.31.0.110'
wsgi_port = 7999


httpclient = ManagerClient(wsgi_url, wsgi_port)

client = GopCdnClient(httpclient)


def show_ports_test():
    print client.show_deploer_ports(agent_id=2)


def cdndomain_search_test():
    print client.cdndomain_search(domain='localhost')


def create_test(entity):

    #     'type': 'object',
    #     'required': ['name', 'etype', 'entity'],
    #     'properties': {
    #         'entity': {'type': 'integer',  'minimum': 1,
    #                    'description': '引用的域名实体id'},
    #         'etype': {'type': 'string', 'description': '资源类型'},
    #         'name': {'type': 'string', 'description': '资源名称'},
    #         'impl': {'type': 'string'},
    #         'auth': {'type': 'object'},
    #         'desc': {'type': 'string'},
    #     }
    # }

    body = {'entity': entity, 'etype': 'ios', 'name': 'cn360',
            'impl': 'websocket', 'desc': '游戏更新文件'}
    print client.cdnresource_create(body=body)


def delete_test(resource_id):
    print client.cdnresource_delete(resource_id=resource_id)


def index_test():
    print client.cdnresource_index()


def show_test(resource_id):
    print client.cdnresource_show(resource_id=resource_id, body={'metadata': True})

def shows_test(resource_id):
    print client.cdnresource_shows(resource_id=resource_id)



# create_test(3)
# delete_test(resource_id=8)
# index_test()
# show_test(resource_id=3)
# shows_test(resource_id=6)

