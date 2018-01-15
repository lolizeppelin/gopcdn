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




def create_test(hostname=None):
    body = {'agent_id': 2}
    if hostname:
        body.update({'domains': [hostname]})
    print client.cdndomain_create(body=body)


def delete_test(entity):
    body = {'agent_id': 2}
    print client.cdndomain_delete(entity=entity)

def index_test():
    for cdn in client.cdnresource_index('mszl')['data']:
        print cdn



def show_test():
    pass


def del_test():
    pass

def upgrade_test():
    pass


# show_ports_test()
# cdndomain_search_test()
create_test('cdn2.awarz.com')
# delete_test(entity=1)