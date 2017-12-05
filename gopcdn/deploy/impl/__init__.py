from simpleutil.config import cfg

from gopcdn.config import endpoint_group

CONF = cfg.CONF


class BaseDeploy(object):

    def __init__(self):
        conf = CONF[endpoint_group.name]
        self.root = conf.nginx_conf
        self.hostname = conf.cdnhost
        self.listen = conf.cdnport
        self.charset = conf.charset
        self.autoindex = conf.autoindex
        self.server = dict()                # map hostname to nginx server obj

    def init_conf(self):
        raise NotImplementedError

    def deploy(self, urlpath, cdnhost, rootpath, configfile):
        raise NotImplementedError