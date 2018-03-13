# -*- coding:utf-8 -*-
from simpleutil.config import cfg
from simpleutil.utils import importutils

from gopcdn import common

CONF = cfg.CONF

IMPLS = {}


class BaseCdnAlias(object):
    def alias(self, path, version):
        raise NotImplementedError

    def _endpoint_name(self):
        """"""
        raise NotImplementedError

    @property
    def namespace(self):
        return self._endpoint_name()


def version_alias(endpoint, path, version):
    try:
        return IMPLS[endpoint].alias(path, version)
    except KeyError:
        raise NotImplementedError('Not impl alias for %s' % endpoint)


def init():
    for import_string in CONF[common.CDN].aliases:
        cls = importutils.import_class(import_string)
        intance = cls()
        if not isinstance(intance, BaseCdnAlias):
            raise TypeError('%s is not sub class of BaseCdnAlias')
        IMPLS[intance.namespace] = intance
