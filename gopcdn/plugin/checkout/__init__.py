# -*- coding:utf-8 -*-
from simpleutil.config import cfg
from simpleutil.utils import importutils

CONF = cfg.CONF


def checkouter(impl):
    """资源检出工具, 默认检出工具为svn"""
    obj = 'gopcdn.plugin.checkout.impl._%s.checkouter' % impl
    return importutils.import_class(obj)
