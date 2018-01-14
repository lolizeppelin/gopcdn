from simpleutil.config import cfg

from gopcdn import common

CONF = cfg.CONF


class BaseDeploy(object):

    def __init__(self):
        conf = CONF[common.CDN]
        self.configdir = conf.configdir
        self.listen = conf.listen
        self.ports = set(conf.ports)
        if not self.ports:
            raise RuntimeError('No ports for Deploy')
        self.character_set = conf.character_set
        self.autoindex = conf.autoindex
        # map hostname to nginx server obj
        self.server = dict()

    def init_conf(self, maps):
        raise NotImplementedError

    def deploy_domian(self, entity, listen, port, charset, domains):
        raise NotImplementedError

    def undeploy_domian(self, entity):
        raise NotImplementedError

    def deploy_resource(self, entity, urlpath, rootpath, configfile):
        raise NotImplementedError

    def undeploy_resource(self, entity, configfile):
        raise NotImplementedError

    def add_hostnames(self, entity, domains):
        raise NotImplementedError

    def remove_hostnames(self, entity, domains):
        raise NotImplementedError

    def reload(self):
        raise NotImplementedError

    def upload(self, filename, overwrite):
        raise NotImplementedError