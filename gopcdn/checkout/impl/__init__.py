from simpleutil.config import cfg
from simpleutil.utils import sysemutils

import subprocess

from gopcdn.config import endpoint_group

CONF = cfg.CONF


class BaseCheckOut(object):

    def __init__(self):
        conf = CONF[endpoint_group.name]
        self.max_time = conf.max_checkout_time

    def init_conf(self):
        raise NotImplementedError

    def deploy(self, urlpath, rootpath, configfile, hostinfo=None):
        raise NotImplementedError