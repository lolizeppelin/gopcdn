from simpleutil.config import cfg

from gopcdn import common

CONF = cfg.CONF


class BaseCheckOut(object):

    def __init__(self):
        conf = CONF[common.CDN]
        self.timeout = conf.checkout_timeout

    def init_conf(self):
        raise NotImplementedError

    def checkout(self, auth, version, rootpath, logfile, timeout, **kwargs):
        raise NotImplementedError

    def cleanup(self, dst, logfile, timeout, **kwargs):
        raise NotImplementedError

    def getversion(self, dst, **kwargs):
        raise NotImplementedError