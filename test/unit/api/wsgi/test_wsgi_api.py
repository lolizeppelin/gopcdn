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

wsgi_url = '127.0.0.1'
wsgi_port = 7999


httpclient = ManagerClient(wsgi_url, wsgi_port)

client = GopCdnClient(httpclient)


def create_test():
    print client.cdnresource_create(endpoint='mszl',
                                    body={'etype': 'ios', 'impl': 'svn',
                                          'name': 'testresource',
                                          'esure': False,
                                          'uri': 'http://172.23.0.2:8081/svn/pokemon_assets_online/default.ios',
                                          'auth': {'username': 'pokemon_op_manager',
                                                   'password': '0bcc3acb7431f3d0'}})

def index_test():
    for cdn in client.cdnresource_index('mszl')['data']:
        print cdn


def show_test():
    for i in range(11, 20):
        print  client.cdnresource_show('mszl', 11)['data']


def del_test():
    print client.cdnresource_delete('mszl', 13)

def upgrade_test():
    print client.cdnresource_upgrade('mszl', 12,
                                     body={'request_time': int(time.time()),
                                           'impl': 'svn',
                                           'esure': False})


upgrade_test()