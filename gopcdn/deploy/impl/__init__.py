from simpleutil.config import cfg

from gopcdn import common

CONF = cfg.CONF


class BaseDeploy(object):

    def __init__(self):
        conf = CONF[common.CDN]
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

    def reload(self):
        raise NotImplementedError