from simpleutil.config import cfg

from gopcdn import common

CONF = cfg.CONF


class BaseUpload(object):
    def __init__(self):
        conf = CONF[common.CDN]
        self.timeout = conf.upload_timeout

    def init_conf(self):
        raise NotImplementedError

    def upload(self, *args, **kwargs):
        raise NotImplementedError

    def postfunc(self, *args, **kwargs):
        raise NotImplementedError
