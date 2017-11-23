from simpleutil.config import cfg

from gopcdn.config import endpoint_group

CONF = cfg.CONF


class BaseCheckOut(object):

    def __init__(self):
        conf = CONF[endpoint_group.name]
        self.timeout = conf.checkout_timeout

    def init_conf(self):
        raise NotImplementedError

    def checkout(self, uri, auth, version, dst, logfile, **kwargs):
        raise NotImplementedError

    def update(self, rootpath, version, auth, logfile, **kwargs):
        raise NotImplementedError